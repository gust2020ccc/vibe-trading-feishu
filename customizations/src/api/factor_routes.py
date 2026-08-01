"""Factor management API routes.

Mounted by ``api_server.py`` via ``register_factor_routes(app, ...)``.

Routes (auth via caller-supplied ``require_auth``):

Factor CRUD:
  GET    /factors                    — list with filters
  POST   /factors                    — create new
  GET    /factors/{fid}              — get by ID
  PUT    /factors/{fid}              — update
  DELETE /factors/{fid}              — delete

Factor marketplace:
  POST   /factors/{fid}/publish      — publish to marketplace
  POST   /factors/{fid}/clone        — clone into own workspace
  POST   /factors/{fid}/rate         — rate (1-5 stars)
  POST   /factors/{fid}/subscribe    — subscribe to updates
  DELETE /factors/{fid}/subscribe    — unsubscribe

Factor portfolios:
  GET    /factors/portfolios         — list portfolios
  POST   /factors/portfolios         — create portfolio
  GET    /factors/portfolios/{pid}   — get portfolio
  PUT    /factors/portfolios/{pid}   — update portfolio
  DELETE /factors/portfolios/{pid}   — delete portfolio
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
class CreateFactorRequest(BaseModel):
    name: str
    source_code: str
    name_en: str = ""
    description: str = ""
    category: str = "custom"
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"
    parent_id: str | None = None


class UpdateFactorRequest(BaseModel):
    name: str | None = None
    source_code: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None
    status: str | None = None
    changelog: str = ""


class RateFactorRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class CloneFactorRequest(BaseModel):
    user_id: str = "anonymous"


class CreatePortfolioRequest(BaseModel):
    name: str
    config: dict[str, Any]
    description: str = ""
    status: str = "draft"


class UpdatePortfolioRequest(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    description: str | None = None
    status: str | None = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_user_id(request: Request) -> str:
    """Extract user_id from request using user_context module."""
    from src.api.user_context import get_user_id_from_request
    return get_user_id_from_request(request)


# --------------------------------------------------------------------------- #
# Route registration
# --------------------------------------------------------------------------- #
def register_factor_routes(app: FastAPI, require_auth: Any = None) -> None:
    """Mount /factors/* routes onto the FastAPI app."""

    if require_auth is None:
        import sys as _sys
        _host = _sys.modules.get("api_server")
        if _host is not None:
            require_auth = getattr(_host, "require_auth", None)
        if require_auth is None:
            def require_auth():  # type: ignore[no-redef]
                return None

    # ================================================================
    # Portfolios (registered first so /factors/portfolios doesn't
    # collide with /factors/{fid})
    # ================================================================
    @app.get("/factors/portfolios", dependencies=[Depends(require_auth)])
    async def list_portfolios(
        request: Request,
        user_id: str | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """List factor portfolios."""
        from src.strategy_manager.service import PortfolioService

        uid = user_id or _get_user_id(request)
        items = PortfolioService.list(user_id=uid, limit=limit, offset=offset)
        return {
            "portfolios": [p.to_dict() for p in items],
            "count": len(items),
        }

    @app.post("/factors/portfolios", dependencies=[Depends(require_auth)])
    async def create_portfolio(
        request: Request,
        body: CreatePortfolioRequest,
    ):
        """Create a new factor portfolio."""
        from src.strategy_manager.service import PortfolioService

        uid = _get_user_id(request)
        portfolio = PortfolioService.create(
            user_id=uid,
            name=body.name,
            config=body.config,
            description=body.description,
            status=body.status,
        )
        return {"portfolio": portfolio.to_dict()}

    @app.get("/factors/portfolios/{pid}", dependencies=[Depends(require_auth)])
    async def get_portfolio(pid: str):
        """Get a single portfolio by ID."""
        from src.strategy_manager.service import PortfolioService

        portfolio = PortfolioService.get(pid)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return {"portfolio": portfolio.to_dict()}

    @app.put("/factors/portfolios/{pid}", dependencies=[Depends(require_auth)])
    async def update_portfolio(pid: str, body: UpdatePortfolioRequest):
        """Update a portfolio."""
        from src.strategy_manager.service import PortfolioService

        portfolio = PortfolioService.update(
            pid,
            name=body.name,
            config=body.config,
            description=body.description,
            status=body.status,
        )
        if portfolio is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return {"portfolio": portfolio.to_dict()}

    @app.delete("/factors/portfolios/{pid}", dependencies=[Depends(require_auth)])
    async def delete_portfolio(pid: str):
        """Delete a portfolio."""
        from src.strategy_manager.service import PortfolioService

        deleted = PortfolioService.delete(pid)
        if not deleted:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return {"deleted": True, "id": pid}

    # ================================================================
    # Factor CRUD
    # ================================================================
    @app.get("/factors", dependencies=[Depends(require_auth)])
    async def list_factors(
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
        """List factors with optional filters."""
        from src.strategy_manager.service import FactorService

        uid = user_id or _get_user_id(request)
        items = FactorService.list(
            user_id=uid if not is_public else None,
            status=status,
            category=category,
            is_public=is_public,
            search=search,
            limit=limit,
            offset=offset,
            include_code=include_code,
        )
        return {
            "factors": [f.to_dict(include_code=include_code) for f in items],
            "count": len(items),
        }

    @app.post("/factors", dependencies=[Depends(require_auth)])
    async def create_factor(
        request: Request,
        body: CreateFactorRequest,
    ):
        """Create a new factor."""
        from src.strategy_manager.service import FactorService

        uid = _get_user_id(request)
        factor, result = FactorService.create(
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
        if factor is None:
            raise HTTPException(status_code=422, detail={
                "message": "Validation failed",
                "errors": result.errors,
                "warnings": result.warnings,
            })
        return {
            "factor": factor.to_dict(include_code=True),
            "validation": {
                "valid": result.valid,
                "warnings": result.warnings,
                "metadata": result.metadata,
            },
        }

    @app.get("/factors/{fid}", dependencies=[Depends(require_auth)])
    async def get_factor(
        fid: str,
        include_code: bool = Query(False),
    ):
        """Get a single factor by ID."""
        from src.strategy_manager.service import FactorService

        factor = FactorService.get(fid, include_code=include_code)
        if factor is None:
            raise HTTPException(status_code=404, detail="Factor not found")
        return {"factor": factor.to_dict(include_code=include_code)}

    @app.put("/factors/{fid}", dependencies=[Depends(require_auth)])
    async def update_factor(fid: str, body: UpdateFactorRequest):
        """Update a factor."""
        from src.strategy_manager.service import FactorService

        factor, result = FactorService.update(
            fid,
            name=body.name,
            source_code=body.source_code,
            description=body.description,
            category=body.category,
            tags=body.tags,
            meta=body.meta,
            status=body.status,
            changelog=body.changelog,
        )
        if factor is None:
            raise HTTPException(status_code=404, detail="Factor not found")
        if not result.valid:
            raise HTTPException(status_code=422, detail={
                "message": "Validation failed",
                "errors": result.errors,
            })
        return {
            "factor": factor.to_dict(include_code=True),
            "validation": {"valid": result.valid, "warnings": result.warnings},
        }

    @app.delete("/factors/{fid}", dependencies=[Depends(require_auth)])
    async def delete_factor(fid: str):
        """Delete a factor."""
        from src.strategy_manager.service import FactorService

        deleted = FactorService.delete(fid)
        if not deleted:
            raise HTTPException(status_code=404, detail="Factor not found")
        return {"deleted": True, "id": fid}

    # ================================================================
    # Factor version management
    # ================================================================
    @app.get("/factors/{fid}/versions", dependencies=[Depends(require_auth)])
    async def list_factor_versions(
        fid: str,
        include_code: bool = Query(False),
    ):
        """List version history for a factor."""
        from src.strategy_manager.service import FactorService

        versions = FactorService.list_versions(fid, include_code=include_code)
        return {
            "versions": [v.to_dict(include_code=include_code) for v in versions],
            "count": len(versions),
        }

    @app.get("/factors/{fid}/versions/{ver}", dependencies=[Depends(require_auth)])
    async def get_factor_version(
        fid: str,
        ver: int,
        include_code: bool = Query(True),
    ):
        """Get a specific factor version snapshot."""
        from src.strategy_manager.service import FactorService

        version = FactorService.get_version(fid, ver)
        if version is None:
            raise HTTPException(status_code=404, detail="Version not found")
        return {"version": version.to_dict(include_code=include_code)}

    @app.post("/factors/{fid}/rollback/{ver}", dependencies=[Depends(require_auth)])
    async def rollback_factor(fid: str, ver: int):
        """Rollback a factor to a previous version (creates new version)."""
        from src.strategy_manager.service import FactorService

        factor, result = FactorService.rollback(fid, ver)
        if factor is None:
            raise HTTPException(status_code=404, detail=result.error_message or "Not found")
        if not result.valid:
            raise HTTPException(status_code=422, detail={"errors": result.errors})
        return {
            "factor": factor.to_dict(include_code=True),
            "rolled_back_to": ver,
        }

    # ================================================================
    # Factor marketplace
    # ================================================================
    @app.post("/factors/{fid}/publish", dependencies=[Depends(require_auth)])
    async def publish_factor(fid: str):
        """Publish a factor to the marketplace."""
        from src.strategy_manager.service import MarketService

        factor = MarketService.publish_factor(fid)
        if factor is None:
            raise HTTPException(status_code=404, detail="Factor not found")
        return {"factor": factor.to_dict()}

    @app.post("/factors/{fid}/clone", dependencies=[Depends(require_auth)])
    async def clone_factor(
        request: Request,
        fid: str,
        body: CloneFactorRequest,
    ):
        """Clone a published factor."""
        from src.strategy_manager.service import MarketService

        uid = body.user_id or _get_user_id(request)
        clone, result = MarketService.clone_factor(fid, uid)
        if clone is None:
            raise HTTPException(status_code=422, detail={
                "message": result.error_message or "Clone failed",
                "errors": result.errors,
            })
        return {"factor": clone.to_dict(include_code=True), "parent_id": fid}

    @app.post("/factors/{fid}/rate", dependencies=[Depends(require_auth)])
    async def rate_factor(
        request: Request,
        fid: str,
        body: RateFactorRequest,
    ):
        """Rate a factor (1-5 stars)."""
        from src.strategy_manager.service import MarketService, FactorService

        uid = _get_user_id(request)
        success = MarketService.rate_factor(fid, uid, body.rating, body.comment)
        if not success:
            raise HTTPException(status_code=422, detail="Rating failed")
        factor = FactorService.get(fid)
        return {
            "rated": True,
            "factor_id": fid,
            "rating_avg": factor.rating_avg if factor else 0,
            "rating_count": factor.rating_count if factor else 0,
        }

    @app.post("/factors/{fid}/subscribe", dependencies=[Depends(require_auth)])
    async def subscribe_factor(
        request: Request,
        fid: str,
        body: CloneFactorRequest | None = None,
    ):
        """Subscribe to a factor's updates."""
        from src.strategy_manager.service import MarketService

        uid = (body.user_id if body else None) or _get_user_id(request)
        success = MarketService.subscribe_factor(fid, uid)
        if not success:
            raise HTTPException(status_code=422, detail="Subscribe failed")
        return {"subscribed": True, "factor_id": fid, "user_id": uid}

    @app.delete("/factors/{fid}/subscribe", dependencies=[Depends(require_auth)])
    async def unsubscribe_factor(
        request: Request,
        fid: str,
        user_id: str | None = Query(None),
    ):
        """Unsubscribe from a factor."""
        from src.strategy_manager.service import MarketService

        uid = user_id or _get_user_id(request)
        success = MarketService.unsubscribe_factor(fid, uid)
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return {"unsubscribed": True, "factor_id": fid, "user_id": uid}
