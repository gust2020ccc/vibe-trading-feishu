"""User isolation middleware for strategy/factor API routes.

Extracts user_id from request headers or query parameters and sets it
on ``request.state.user_id`` so that all CRUD operations are scoped
to the authenticated user.

In development mode (no API key configured), defaults to 'anonymous'.

Sprint 4 enhances this to integrate with the existing usage/auth system:
  - Bearer token → resolve to user_id via usage.UserService
  - X-User-Id header → direct user_id (admin/testing only)
  - Query param ?user_id= → fallback (dev mode only)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)

# Header names for user identification
_USER_ID_HEADER = "X-User-Id"
_USER_ID_QUERY = "user_id"


def get_user_id_from_request(request: Request) -> str:
    """Extract user_id from request, with multiple fallback strategies.

    Priority:
      1. X-User-Id header (if present and non-empty)
      2. request.state.user_id (set by upstream auth middleware)
      3. ?user_id= query param (dev/testing only)
      4. 'anonymous' (fallback)

    In production (Sprint 5+), the Bearer token will be resolved to a
    user_id via the usage.UserService, and X-User-Id will be restricted
    to admin role only.
    """
    # 1. Header
    header_uid = request.headers.get(_USER_ID_HEADER)
    if header_uid and header_uid.strip():
        return header_uid.strip()

    # 2. request.state (set by middleware)
    state_uid = getattr(request.state, "user_id", None)
    if state_uid and isinstance(state_uid, str) and state_uid.strip():
        return state_uid.strip()

    # 3. Query param (dev mode)
    query_uid = request.query_params.get(_USER_ID_QUERY)
    if query_uid and query_uid.strip():
        return query_uid.strip()

    # 4. Fallback
    return "anonymous"


def create_user_middleware():
    """Return a middleware function that sets request.state.user_id.

    Usage::

        app.middleware("http")(create_user_middleware())
    """
    async def user_context_middleware(request: Request, call_next):
        """Set user_id on request state for downstream handlers."""
        request.state.user_id = get_user_id_from_request(request)
        response = await call_next(request)
        return response

    return user_context_middleware


def require_user_id(request: Request) -> str:
    """FastAPI dependency that returns the authenticated user_id.

    Raises 401 if no user_id could be determined (i.e., 'anonymous'
    is treated as unauthenticated for user-scoped operations).

    For marketplace browsing (public strategies), use
    :func:`get_user_id_from_request` instead, which allows 'anonymous'.
    """
    uid = get_user_id_from_request(request)
    if uid == "anonymous":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide X-User-Id header or Bearer token.",
        )
    return uid
