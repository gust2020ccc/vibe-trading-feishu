"""Strategy & Factor management API routes.

Mounted by ``api_server.py`` via ``register_strategy_routes(app, ...)``.

Routes (auth via caller-supplied ``require_auth``):

Strategy CRUD:
  GET    /strategies                 — list with filters
  POST   /strategies                 — create new
  GET    /strategies/{sid}           — get by ID
  PUT    /strategies/{sid}           — update
  DELETE /strategies/{sid}           — delete

Strategy versions:
  GET    /strategies/{sid}/versions  — list version history
  GET    /strategies/{sid}/versions/{ver} — get specific version
  POST   /strategies/{sid}/rollback/{ver} — rollback to version

Strategy marketplace:
  POST   /strategies/{sid}/publish   — publish to marketplace
  POST   /strategies/{sid}/archive   — archive
  POST   /strategies/{sid}/clone     — clone into own workspace
  POST   /strategies/{sid}/subscribe — subscribe to updates
  DELETE /strategies/{sid}/subscribe — unsubscribe
  POST   /strategies/{sid}/rate      — rate (1-5 stars)

Strategy templates:
  GET    /strategies/templates       — list available system templates
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Request / Response models
# --------------------------------------------------------------------------- #
class CreateStrategyRequest(BaseModel):
    name: str
    source_code: str
    name_en: str = ""
    description: str = ""
    category: str = "custom"
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"
    parent_id: str | None = None


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    source_code: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None
    status: str | None = None
    changelog: str = ""


class RateStrategyRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class CloneRequest(BaseModel):
    user_id: str = "anonymous"


class SubscribeRequest(BaseModel):
    user_id: str = "anonymous"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_user_id(request: Request) -> str:
    """Extract user_id from request state or query, fallback to 'anonymous'."""
    # In Sprint 4, this will use proper auth-based user isolation
    return getattr(request.state, "user_id", None) or "anonymous"


# --------------------------------------------------------------------------- #
# Route registration
# --------------------------------------------------------------------------- #
def register_strategy_routes(app: FastAPI, require_auth: Any = None) -> None:
    """Mount /strategies/* routes onto the FastAPI app."""

    if require_auth is None:
        import sys as _sys
        _host = _sys.modules.get("api_server")
        if _host is not None:
            require_auth = getattr(_host, "require_auth", None)
        if require_auth is None:
            def require_auth():  # type: ignore[no-redef]
                return None

    # ================================================================
    # Templates
    # ================================================================
    @app.get("/strategies/templates", dependencies=[Depends(require_auth)])
    async def list_strategy_templates():
        """List all available strategy templates (system + custom + db)."""
        from src.backtest.templates import list_strategies
        return {"strategies": list_strategies()}

    # ================================================================
    # CRUD
    # ================================================================
    @app.get("/strategies", dependencies=[Depends(require_auth)])
    async def list_strategies(
        request: Request,
        user_id: str | None = Query(None),
        status: str | None = Query(None),
        category: str | None = Query(None),
        is_public: bool | None = Query(None),
        search: str | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        include_code: bool = Query(False),
    ):
        """List strategies with optional filters."""
        from src.strategy_manager.service import StrategyService

        uid = user_id or _get_user_id(request)
        items = StrategyService.list(
            user_id=uid if not is_public else None,
            status=status,
            category=category,
            is_public=is_public,
            search=search,
            limit=limit,
            offset=offset,
            include_code=include_code,
        )
        total = StrategyService.count(user_id=uid if not is_public else None, status=status)
        return {
            "strategies": [s.to_dict(include_code=include_code) for s in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.post("/strategies", dependencies=[Depends(require_auth)])
    async def create_strategy(
        request: Request,
        body: CreateStrategyRequest,
    ):
        """Create a new strategy."""
        from src.strategy_manager.service import StrategyService

        uid = _get_user_id(request)
        strategy, result = StrategyService.create(
            user_id=uid,
            name=body.name,
            source_code=body.source_code,
            name_en=body.name_en,
            description=body.description,
            category=body.category,
            tags=body.tags,
            meta=body.meta,
            status=body.status,
            parent_id=body.parent_id,
        )
        if strategy is None:
            raise HTTPException(status_code=422, detail={
                "message": "Validation failed",
                "errors": result.errors,
                "warnings": result.warnings,
            })
        return {
            "strategy": strategy.to_dict(include_code=True),
            "validation": {
                "valid": result.valid,
                "warnings": result.warnings,
                "metadata": result.metadata,
            },
        }

    @app.get("/strategies/{sid}", dependencies=[Depends(require_auth)])
    async def get_strategy(
        sid: str,
        include_code: bool = Query(False),
    ):
        """Get a single strategy by ID."""
        from src.strategy_manager.service import StrategyService

        strategy = StrategyService.get(sid, include_code=include_code)
        if strategy is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"strategy": strategy.to_dict(include_code=include_code)}

    @app.put("/strategies/{sid}", dependencies=[Depends(require_auth)])
    async def update_strategy(
        sid: str,
        body: UpdateStrategyRequest,
    ):
        """Update a strategy. Source code changes trigger version increment."""
        from src.strategy_manager.service import StrategyService

        strategy, result = StrategyService.update(
            sid,
            name=body.name,
            source_code=body.source_code,
            description=body.description,
            category=body.category,
            tags=body.tags,
            meta=body.meta,
            status=body.status,
            changelog=body.changelog,
        )
        if strategy is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        if not result.valid:
            raise HTTPException(status_code=422, detail={
                "message": "Validation failed",
                "errors": result.errors,
            })
        return {
            "strategy": strategy.to_dict(include_code=True),
            "validation": {
                "valid": result.valid,
                "warnings": result.warnings,
            },
        }

    @app.delete("/strategies/{sid}", dependencies=[Depends(require_auth)])
    async def delete_strategy(sid: str):
        """Delete a strategy and all its versions."""
        from src.strategy_manager.service import StrategyService

        deleted = StrategyService.delete(sid)
        if not deleted:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"deleted": True, "id": sid}

    # ================================================================
    # Version management
    # ================================================================
    @app.get("/strategies/{sid}/versions", dependencies=[Depends(require_auth)])
    async def list_strategy_versions(
        sid: str,
        include_code: bool = Query(False),
    ):
        """List version history for a strategy."""
        from src.strategy_manager.service import StrategyService

        versions = StrategyService.list_versions(sid, include_code=include_code)
        return {
            "versions": [v.to_dict(include_code=include_code) for v in versions],
            "count": len(versions),
        }

    @app.get("/strategies/{sid}/versions/{ver}", dependencies=[Depends(require_auth)])
    async def get_strategy_version(
        sid: str,
        ver: int,
        include_code: bool = Query(True),
    ):
        """Get a specific version snapshot."""
        from src.strategy_manager.service import StrategyService

        version = StrategyService.get_version(sid, ver)
        if version is None:
            raise HTTPException(status_code=404, detail="Version not found")
        return {"version": version.to_dict(include_code=include_code)}

    @app.post("/strategies/{sid}/rollback/{ver}", dependencies=[Depends(require_auth)])
    async def rollback_strategy(sid: str, ver: int):
        """Rollback a strategy to a previous version (creates new version)."""
        from src.strategy_manager.service import StrategyService

        strategy, result = StrategyService.rollback(sid, ver)
        if strategy is None:
            raise HTTPException(status_code=404, detail=result.error_message or "Not found")
        if not result.valid:
            raise HTTPException(status_code=422, detail={
                "errors": result.errors,
            })
        return {
            "strategy": strategy.to_dict(include_code=True),
            "rolled_back_to": ver,
        }

    # ================================================================
    # Marketplace
    # ================================================================
    @app.post("/strategies/{sid}/publish", dependencies=[Depends(require_auth)])
    async def publish_strategy(sid: str):
        """Publish a strategy to the marketplace."""
        from src.strategy_manager.service import MarketService

        strategy = MarketService.publish_strategy(sid)
        if strategy is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"strategy": strategy.to_dict()}

    @app.post("/strategies/{sid}/archive", dependencies=[Depends(require_auth)])
    async def archive_strategy(sid: str):
        """Archive a strategy."""
        from src.strategy_manager.service import MarketService

        strategy = MarketService.archive_strategy(sid)
        if strategy is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"strategy": strategy.to_dict()}

    @app.post("/strategies/{sid}/clone", dependencies=[Depends(require_auth)])
    async def clone_strategy(
        request: Request,
        sid: str,
        body: CloneRequest,
    ):
        """Clone a published strategy into your workspace."""
        from src.strategy_manager.service import MarketService

        uid = body.user_id or _get_user_id(request)
        clone, result = MarketService.clone_strategy(sid, uid)
        if clone is None:
            raise HTTPException(status_code=422, detail={
                "message": result.error_message or "Clone failed",
                "errors": result.errors,
            })
        return {
            "strategy": clone.to_dict(include_code=True),
            "parent_id": sid,
        }

    @app.post("/strategies/{sid}/subscribe", dependencies=[Depends(require_auth)])
    async def subscribe_strategy(
        request: Request,
        sid: str,
        body: SubscribeRequest,
    ):
        """Subscribe to a strategy's updates."""
        from src.strategy_manager.service import MarketService

        uid = body.user_id or _get_user_id(request)
        success = MarketService.subscribe_strategy(sid, uid)
        if not success:
            raise HTTPException(status_code=422, detail="Subscribe failed")
        return {"subscribed": True, "strategy_id": sid, "user_id": uid}

    @app.delete("/strategies/{sid}/subscribe", dependencies=[Depends(require_auth)])
    async def unsubscribe_strategy(
        request: Request,
        sid: str,
        user_id: str = Query(...),
    ):
        """Unsubscribe from a strategy."""
        from src.strategy_manager.service import MarketService

        success = MarketService.unsubscribe_strategy(sid, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return {"subscribed": False, "strategy_id": sid}

    @app.post("/strategies/{sid}/rate", dependencies=[Depends(require_auth)])
    async def rate_strategy(
        request: Request,
        sid: str,
        body: RateStrategyRequest,
    ):
        """Rate a strategy (1-5 stars)."""
        from src.strategy_manager.service import MarketService, StrategyService

        uid = _get_user_id(request)
        success = MarketService.rate_strategy(sid, uid, body.rating, body.comment)
        if not success:
            raise HTTPException(status_code=422, detail="Rating failed")
        strategy = StrategyService.get(sid)
        return {
            "rated": True,
            "strategy_id": sid,
            "rating_avg": strategy.rating_avg if strategy else 0,
            "rating_count": strategy.rating_count if strategy else 0,
        }

    # ================================================================
    # Migration
    # ================================================================
    @app.post("/strategies/migrate", dependencies=[Depends(require_auth)])
    async def migrate_custom_strategies(dry_run: bool = Query(False)):
        """Migrate file-based custom strategies into the database."""
        from src.strategy_manager.migration import migrate_custom_strategies

        report = migrate_custom_strategies(dry_run=dry_run)
        return {
            "summary": report.summary(),
            "scanned": report.scanned,
            "created": report.created,
            "skipped": report.skipped,
            "failed": report.failed,
            "entries": [
                {
                    "filename": e.filename,
                    "strategy_id": e.strategy_id,
                    "status": e.status,
                    "db_id": e.db_id,
                    "error": e.error,
                }
                for e in report.entries
            ],
        }
