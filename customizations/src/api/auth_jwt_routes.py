"""JWT Authentication routes for the Vibe Trading platform.

Provides:
  - POST /auth/register  — register a new user with email + password
  - POST /auth/login     — login with email + password, returns JWT
  - GET  /auth/me        — get current user info from JWT
  - POST /auth/refresh   — refresh an expiring JWT

Password hashing uses hashlib.pbkdf2_hmac (no external deps).
JWT tokens are signed with HS256 using a secret key derived from the
environment or auto-generated on first run.

The ``get_current_user`` dependency can be used by other route modules
to require JWT authentication instead of the loopback/API-key auth.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any

import jwt
from fastapi import Body, Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_SECONDS = 7 * 24 * 3600   # 7 days
_PBKDF2_ITERATIONS = 120_000
_PBKDF2_KEY_LEN = 32

# Cache for the secret key
_jwt_secret: str | None = None


def _get_jwt_secret() -> str:
    """Get or generate the JWT signing secret.

    Priority:
      1. VIBE_TRADING_JWT_SECRET env var
      2. Persisted in ~/.vibe-trading/.jwt_secret (auto-generated)
    """
    global _jwt_secret
    if _jwt_secret:
        return _jwt_secret

    env_secret = os.environ.get("VIBE_TRADING_JWT_SECRET", "").strip()
    if env_secret:
        _jwt_secret = env_secret
        return _jwt_secret

    # Try to load from file
    from src.config.paths import get_data_dir

    secret_path = get_data_dir() / ".jwt_secret"
    if secret_path.exists():
        try:
            val = secret_path.read_text(encoding="utf-8").strip()
            if val:
                _jwt_secret = val
                return _jwt_secret
        except Exception:
            pass

    # Generate and persist
    _jwt_secret = secrets.token_urlsafe(48)
    try:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_text(_jwt_secret, encoding="utf-8")
        # Restrict file permissions (best-effort on Windows)
        try:
            os.chmod(secret_path, 0o600)
        except Exception:
            pass
    except Exception:
        logger.warning("Failed to persist JWT secret — will regenerate on restart")

    return _jwt_secret


# ============================================================================
# Password hashing (PBKDF2-HMAC-SHA256, no external deps)
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Returns: ``pbkdf2$<iterations>$<salt_hex>$<hash_hex>``
    """
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                             _PBKDF2_ITERATIONS, _PBKDF2_KEY_LEN)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash string."""
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2":
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                             iterations, len(expected))
    return hmac.compare_digest(dk, expected)


# ============================================================================
# JWT token utilities
# ============================================================================

def create_access_token(user_id: str, role: str, expires_in: int = _JWT_EXPIRE_SECONDS) -> str:
    """Create a JWT access token for the given user."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _extract_bearer_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and validate JWT, return user dict.

    Usage in routes::

        @app.get("/protected")
        async def protected(user: dict = Depends(get_current_user)):
            user_id = user["user_id"]
            ...
    """
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub", "")

    # Load user from DB to verify they still exist and are active
    from src.api.state import _get_usage_service
    svc = _get_usage_service()
    if svc is None:
        raise HTTPException(status_code=503, detail="User service unavailable")

    user = svc.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    # Also set on request.state for downstream user_context
    request.state.user_id = user_id

    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
    }


async def get_optional_user(request: Request) -> dict | None:
    """Like get_current_user but returns None instead of raising 401.
    Useful for routes that work for both authenticated and anonymous users.
    """
    token = _extract_bearer_token(request)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None

    user_id = payload.get("sub", "")
    from src.api.state import _get_usage_service
    svc = _get_usage_service()
    if svc is None:
        return None
    user = svc.get_user(user_id)
    if user is None or user.status == "disabled":
        return None

    request.state.user_id = user_id
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
    }


# ============================================================================
# Request / Response models
# ============================================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class MeResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    status: str


# ============================================================================
# Route registration
# ============================================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def register_auth_jwt_routes(app: FastAPI) -> None:
    """Register JWT authentication routes onto the FastAPI app.

    Note: This is named ``register_auth_jwt_routes`` to avoid collision with
    the existing ``register_auth_routes`` (SSE tickets) in auth_routes.py.
    """

    def _svc():
        from src.api.state import _get_usage_service
        svc = _get_usage_service()
        if svc is None:
            raise HTTPException(status_code=503, detail="User service unavailable")
        return svc

    # ================================================================
    # POST /auth/register
    # ================================================================

    def _count_users_with_password() -> int:
        """Count users that have a password set (i.e., registered via web)."""
        from src.usage.db import get_connection
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM users WHERE password_hash != ''"
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def _count_admins() -> int:
        """Count users with admin role that have a password (web-accessible)."""
        from src.usage.db import get_connection
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin' AND password_hash != ''"
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    @app.post("/auth/register")
    async def register(req: RegisterRequest):
        svc = _svc()

        # Validate password strength
        if len(req.password) < 6:
            raise HTTPException(status_code=422, detail="Password must be at least 6 characters")

        # Check if email already registered
        conn = None
        try:
            from src.usage.db import get_connection
            conn = get_connection()
            existing = conn.execute(
                "SELECT user_id FROM users WHERE email = ? AND email != ''",
                (req.email.lower(),),
            ).fetchone()
        finally:
            if conn:
                conn.close()

        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        # First registered user (with password) auto-becomes admin if no admins exist
        is_first_admin = (_count_users_with_password() == 0 and _count_admins() == 0)

        # Create user_id (use email prefix + random suffix for uniqueness)
        base = req.email.split("@")[0][:20]
        user_id = f"{base}_{secrets.token_hex(4)}"

        # Ensure user_id is unique
        while svc.get_user(user_id) is not None:
            user_id = f"{base}_{secrets.token_hex(4)}"

        # Create the user
        user = svc.get_or_create_user(user_id, "web", req.name or req.email.split("@")[0])

        # First registered user auto-becomes admin
        if is_first_admin:
            user = svc.update_user(user_id, role="admin")

        # Set email and password hash
        pw_hash = hash_password(req.password)
        now = _now_iso()
        from src.usage.db import get_connection
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE users SET email = ?, password_hash = ?, updated_at = ? WHERE user_id = ?",
                (req.email.lower(), pw_hash, now, user_id),
            )
            conn.commit()
        finally:
            conn.close()

        # Generate token
        token = create_access_token(user_id, user.role)

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": user_id,
                "name": user.name,
                "email": req.email.lower(),
                "role": user.role,
                "status": user.status,
            },
            "is_first_admin": is_first_admin,
        }

    # ================================================================
    # GET /auth/setup-status
    # ================================================================

    @app.get("/auth/setup-status")
    async def setup_status():
        """Check if the system needs initial admin setup.

        Returns:
          - needs_setup: true if no admin exists yet
          - total_users: total registered users count
        """
        return {
            "needs_setup": _count_admins() == 0,
            "total_users": _count_users_with_password(),
        }

    # ================================================================
    # POST /auth/login
    # ================================================================

    @app.post("/auth/login")
    async def login(req: LoginRequest):
        svc = _svc()

        # Find user by email
        from src.usage.db import get_connection
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ? AND email != ''",
                (req.email.lower(),),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password
        stored_hash = row["password_hash"] if "password_hash" in row.keys() else ""
        if not stored_hash or not verify_password(req.password, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Check user status
        if row["status"] == "disabled":
            raise HTTPException(status_code=403, detail="Account disabled. Contact admin.")

        user_id = row["user_id"]
        role = row["role"]

        # Update last login timestamp
        now = _now_iso()
        conn = get_connection()
        try:
            conn.execute("UPDATE users SET updated_at = ? WHERE user_id = ?", (now, user_id))
            conn.commit()
        finally:
            conn.close()

        token = create_access_token(user_id, role)

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": user_id,
                "name": row["name"],
                "email": row["email"],
                "role": role,
                "status": row["status"],
            },
        }

    # ================================================================
    # GET /auth/me
    # ================================================================

    @app.get("/auth/me")
    async def get_me(user: dict = Depends(get_current_user)):
        return user

    # ================================================================
    # POST /auth/refresh
    # ================================================================

    @app.post("/auth/refresh")
    async def refresh_token(user: dict = Depends(get_current_user)):
        """Issue a new token for an authenticated user (extends session)."""
        token = create_access_token(user["user_id"], user["role"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user,
        }

    # ================================================================
    # POST /auth/change-password
    # ================================================================

    @app.post("/auth/change-password")
    async def change_password(
        old_password: str = Body(..., embed=True),
        new_password: str = Body(..., embed=True),
        user: dict = Depends(get_current_user),
    ):
        if len(new_password) < 6:
            raise HTTPException(status_code=422, detail="Password must be at least 6 characters")

        from src.usage.db import get_connection
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE user_id = ?",
                (user["user_id"],),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="User not found")

            if not verify_password(old_password, row["password_hash"]):
                raise HTTPException(status_code=401, detail="Current password is incorrect")

            new_hash = hash_password(new_password)
            now = _now_iso()
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?",
                (new_hash, now, user["user_id"]),
            )
            conn.commit()
        finally:
            conn.close()

        return {"status": "ok", "message": "Password changed"}

    logger.info("JWT auth routes registered: /auth/register, /auth/login, /auth/me, /auth/refresh, /auth/change-password")
