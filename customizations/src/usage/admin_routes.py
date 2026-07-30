"""Admin Web API routes for user management and usage tracking.

All routes require authentication via require_auth.
Follows the existing register_xxx_routes(app) pattern.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CreateUserRequest(BaseModel):
    user_id: str
    name: str = ""
    channel: str = "feishu"
    role: str = "user"


class UpdateUserRequest(BaseModel):
    status: str | None = None
    role: str | None = None
    name: str | None = None


class UpdateQuotaRequest(BaseModel):
    daily_token_limit: int | None = None
    monthly_token_limit: int | None = None
    concurrent_session_limit: int | None = None
    rate_limit_per_minute: int | None = None


def register_admin_routes(app: FastAPI, require_auth: Any = None) -> None:
    """Mount /admin/* routes onto the FastAPI app."""

    if require_auth is None:
        import sys as _sys
        _host = _sys.modules.get("api_server")
        if _host is not None:
            require_auth = getattr(_host, "require_auth", None)
        if require_auth is None:
            # Fallback: allow all if no auth configured (dev mode)
            def require_auth():  # type: ignore[no-redef]
                return None

    def _svc():
        from src.api.state import _get_usage_service
        svc = _get_usage_service()
        if svc is None:
            raise HTTPException(status_code=503, detail="Usage service not available")
        return svc

    # ================================================================
    # Dashboard (HTML)
    # ================================================================

    @app.get("/admin/dashboard", dependencies=[Depends(require_auth)])
    async def admin_dashboard():
        from src.usage.dashboard import get_dashboard_html
        return HTMLResponse(content=get_dashboard_html())

    # ================================================================
    # User Management
    # ================================================================

    @app.get("/admin/users", dependencies=[Depends(require_auth)])
    async def list_users():
        svc = _svc()
        return svc.get_users_with_usage()

    @app.post("/admin/users", dependencies=[Depends(require_auth)])
    async def create_user(req: CreateUserRequest):
        svc = _svc()
        user = svc.get_or_create_user(req.user_id, req.channel, req.name)
        if req.role != "user":
            user = svc.update_user(req.user_id, role=req.role)
        return {"status": "ok", "user": _user_dict(user)}

    @app.get("/admin/users/{user_id}", dependencies=[Depends(require_auth)])
    async def get_user(user_id: str):
        svc = _svc()
        user = svc.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        summary = svc.get_usage_summary(user_id)
        return {
            "user": _user_dict(user),
            "usage": {
                "today_tokens": summary.today_tokens,
                "month_tokens": summary.month_tokens,
                "today_requests": summary.today_requests,
                "month_requests": summary.month_requests,
            },
            "quota": _quota_dict(summary.quota) if summary.quota else None,
        }

    @app.put("/admin/users/{user_id}", dependencies=[Depends(require_auth)])
    async def update_user(user_id: str, req: UpdateUserRequest):
        svc = _svc()
        fields = {k: v for k, v in req.model_dump().items() if v is not None}
        user = svc.update_user(user_id, **fields)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "ok", "user": _user_dict(user)}

    @app.delete("/admin/users/{user_id}", dependencies=[Depends(require_auth)])
    async def delete_user(user_id: str):
        svc = _svc()
        if not svc.delete_user(user_id):
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "ok", "deleted": user_id}

    # ================================================================
    # Quota Management
    # ================================================================

    @app.get("/admin/users/{user_id}/quota", dependencies=[Depends(require_auth)])
    async def get_quota(user_id: str):
        svc = _svc()
        return _quota_dict(svc.get_quota(user_id))

    @app.put("/admin/users/{user_id}/quota", dependencies=[Depends(require_auth)])
    async def set_quota(user_id: str, req: UpdateQuotaRequest):
        svc = _svc()
        fields = {k: v for k, v in req.model_dump().items() if v is not None}
        quota = svc.set_quota(user_id, **fields)
        return {"status": "ok", "quota": _quota_dict(quota)}

    # ================================================================
    # Usage Queries
    # ================================================================

    @app.get("/admin/users/{user_id}/usage", dependencies=[Depends(require_auth)])
    async def get_user_usage(user_id: str, date_from: str = "", date_to: str = "", limit: int = 50):
        svc = _svc()
        return svc.get_usage_records(user_id, date_from, date_to, limit)

    @app.get("/admin/usage/summary", dependencies=[Depends(require_auth)])
    async def usage_summary():
        svc = _svc()
        return svc.get_global_summary()

    @app.get("/admin/usage/daily", dependencies=[Depends(require_auth)])
    async def usage_daily(date_from: str = "", date_to: str = ""):
        svc = _svc()
        return svc.get_daily_aggregates(date_from, date_to)


def _user_dict(user) -> dict:
    return {
        "user_id": user.user_id,
        "name": user.name,
        "channel": user.channel,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _quota_dict(quota) -> dict:
    return {
        "user_id": quota.user_id,
        "daily_token_limit": quota.daily_token_limit,
        "monthly_token_limit": quota.monthly_token_limit,
        "concurrent_session_limit": quota.concurrent_session_limit,
        "rate_limit_per_minute": quota.rate_limit_per_minute,
    }
