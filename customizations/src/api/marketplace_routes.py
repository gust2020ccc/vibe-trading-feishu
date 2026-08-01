"""Marketplace browsing API routes.

Dedicated endpoints for browsing published strategies and factors with
sorting by popularity, rating, recency, and clone count.

Routes (auth via caller-supplied ``require_auth``):

  GET /marketplace/strategies           — browse published strategies
  GET /marketplace/factors              — browse published factors
  GET /marketplace/strategies/featured  — top-rated + most-subscribed
  GET /marketplace/factors/featured     — top-rated + most-subscribed
  GET /marketplace/stats                — marketplace overview stats
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_user_id(request: Request) -> str:
    """Extract user_id from request using user_context module."""
    from src.api.user_context import get_user_id_from_request
    return get_user_id_from_request(request)


_SORT_MAP_STRATEGY = {
    "popular": "subscriber_count DESC",
    "rating": "rating_avg DESC, rating_count DESC",
    "recent": "updated_at DESC",
    "clones": "clone_count DESC",
    "name": "name ASC",
}

_SORT_MAP_FACTOR = {
    "popular": "subscriber_count DESC",
    "rating": "rating_avg DESC, rating_count DESC",
    "recent": "updated_at DESC",
    "clones": "clone_count DESC",
    "name": "name ASC",
}


# --------------------------------------------------------------------------- #
# Route registration
# --------------------------------------------------------------------------- #
def register_marketplace_routes(app: FastAPI, require_auth: Any = None) -> None:
    """Mount /marketplace/* routes onto the FastAPI app."""

    if require_auth is None:
        import sys as _sys
        _host = _sys.modules.get("api_server")
        if _host is not None:
            require_auth = getattr(_host, "require_auth", None)
        if require_auth is None:
            def require_auth():  # type: ignore[no-redef]
                return None

    # ================================================================
    # Browse published strategies
    # ================================================================
    @app.get("/marketplace/strategies", dependencies=[Depends(require_auth)])
    async def browse_strategies(
        request: Request,
        sort: str = Query("popular", regex="^(popular|rating|recent|clones|name)$"),
        category: str | None = Query(None),
        search: str | None = Query(None),
        tag: str | None = Query(None),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        """Browse published strategies in the marketplace.

        Sort options: popular (subscribers), rating, recent, clones, name.
        """
        from src.strategy_manager import db

        db.ensure_db()
        order_by = _SORT_MAP_STRATEGY.get(sort, "subscriber_count DESC")

        clauses = ["is_public = 1", "status = 'published'"]
        params: list[Any] = []

        if category:
            clauses.append("category = ?")
            params.append(category)
        if search:
            clauses.append("(name LIKE ? OR description LIKE ? OR market_desc LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

        where = " WHERE " + " AND ".join(clauses)
        query = f"""SELECT * FROM strategies{where}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?"""
        params.extend([limit, offset])

        conn = db.get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
            count_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM strategies{where}", params[:-2]
            ).fetchone()
        finally:
            conn.close()

        from src.strategy_manager.service import _row_to_strategy
        items = []
        for r in rows:
            s = _row_to_strategy(r)
            s.source_code = ""  # never expose code in marketplace browse
            items.append(s.to_dict())

        return {
            "strategies": items,
            "count": len(items),
            "total": count_row["cnt"] if count_row else 0,
            "sort": sort,
        }

    # ================================================================
    # Browse published factors
    # ================================================================
    @app.get("/marketplace/factors", dependencies=[Depends(require_auth)])
    async def browse_factors(
        request: Request,
        sort: str = Query("popular", regex="^(popular|rating|recent|clones|name)$"),
        category: str | None = Query(None),
        search: str | None = Query(None),
        tag: str | None = Query(None),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        """Browse published factors in the marketplace."""
        from src.strategy_manager import db

        db.ensure_db()
        order_by = _SORT_MAP_FACTOR.get(sort, "subscriber_count DESC")

        clauses = ["is_public = 1", "status = 'published'"]
        params: list[Any] = []

        if category:
            clauses.append("category = ?")
            params.append(category)
        if search:
            clauses.append("(name LIKE ? OR description LIKE ? OR market_desc LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

        where = " WHERE " + " AND ".join(clauses)
        query = f"""SELECT * FROM factors{where}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?"""
        params.extend([limit, offset])

        conn = db.get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
            count_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM factors{where}", params[:-2]
            ).fetchone()
        finally:
            conn.close()

        from src.strategy_manager.service import _row_to_factor
        items = []
        for r in rows:
            f = _row_to_factor(r)
            f.source_code = ""
            items.append(f.to_dict())

        return {
            "factors": items,
            "count": len(items),
            "total": count_row["cnt"] if count_row else 0,
            "sort": sort,
        }

    # ================================================================
    # Featured (top-rated + most-subscribed)
    # ================================================================
    @app.get("/marketplace/strategies/featured", dependencies=[Depends(require_auth)])
    async def featured_strategies(
        limit: int = Query(5, ge=1, le=20),
    ):
        """Get featured strategies (top-rated + most-subscribed)."""
        from src.strategy_manager import db

        db.ensure_db()
        conn = db.get_connection()
        try:
            # Top rated
            top_rated = conn.execute(
                """SELECT * FROM strategies
                   WHERE is_public = 1 AND status = 'published' AND rating_count >= 1
                   ORDER BY rating_avg DESC, rating_count DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            # Most subscribed
            top_subscribed = conn.execute(
                """SELECT * FROM strategies
                   WHERE is_public = 1 AND status = 'published'
                   ORDER BY subscriber_count DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            # Most cloned
            top_cloned = conn.execute(
                """SELECT * FROM strategies
                   WHERE is_public = 1 AND status = 'published'
                   ORDER BY clone_count DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            conn.close()

        from src.strategy_manager.service import _row_to_strategy

        def _to_list(rows):
            items = []
            for r in rows:
                s = _row_to_strategy(r)
                s.source_code = ""
                items.append(s.to_dict())
            return items

        return {
            "top_rated": _to_list(top_rated),
            "top_subscribed": _to_list(top_subscribed),
            "top_cloned": _to_list(top_cloned),
        }

    @app.get("/marketplace/factors/featured", dependencies=[Depends(require_auth)])
    async def featured_factors(
        limit: int = Query(5, ge=1, le=20),
    ):
        """Get featured factors (top-rated + most-subscribed)."""
        from src.strategy_manager import db

        db.ensure_db()
        conn = db.get_connection()
        try:
            top_rated = conn.execute(
                """SELECT * FROM factors
                   WHERE is_public = 1 AND status = 'published' AND rating_count >= 1
                   ORDER BY rating_avg DESC, rating_count DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            top_subscribed = conn.execute(
                """SELECT * FROM factors
                   WHERE is_public = 1 AND status = 'published'
                   ORDER BY subscriber_count DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            top_cloned = conn.execute(
                """SELECT * FROM factors
                   WHERE is_public = 1 AND status = 'published'
                   ORDER BY clone_count DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            conn.close()

        from src.strategy_manager.service import _row_to_factor

        def _to_list(rows):
            items = []
            for r in rows:
                f = _row_to_factor(r)
                f.source_code = ""
                items.append(f.to_dict())
            return items

        return {
            "top_rated": _to_list(top_rated),
            "top_subscribed": _to_list(top_subscribed),
            "top_cloned": _to_list(top_cloned),
        }

    # ================================================================
    # Marketplace stats
    # ================================================================
    @app.get("/marketplace/stats", dependencies=[Depends(require_auth)])
    async def marketplace_stats():
        """Get marketplace overview statistics."""
        from src.strategy_manager import db

        db.ensure_db()
        conn = db.get_connection()
        try:
            s_published = conn.execute(
                "SELECT COUNT(*) as cnt FROM strategies WHERE is_public = 1 AND status = 'published'"
            ).fetchone()
            s_total_subs = conn.execute(
                "SELECT COALESCE(SUM(subscriber_count), 0) as cnt FROM strategies WHERE is_public = 1"
            ).fetchone()
            s_total_clones = conn.execute(
                "SELECT COALESCE(SUM(clone_count), 0) as cnt FROM strategies WHERE is_public = 1"
            ).fetchone()
            s_avg_rating = conn.execute(
                "SELECT COALESCE(AVG(rating_avg), 0) as avg_r FROM strategies WHERE rating_count > 0 AND is_public = 1"
            ).fetchone()

            f_published = conn.execute(
                "SELECT COUNT(*) as cnt FROM factors WHERE is_public = 1 AND status = 'published'"
            ).fetchone()
            f_total_subs = conn.execute(
                "SELECT COALESCE(SUM(subscriber_count), 0) as cnt FROM factors WHERE is_public = 1"
            ).fetchone()
            f_total_clones = conn.execute(
                "SELECT COALESCE(SUM(clone_count), 0) as cnt FROM factors WHERE is_public = 1"
            ).fetchone()
            f_avg_rating = conn.execute(
                "SELECT COALESCE(AVG(rating_avg), 0) as avg_r FROM factors WHERE rating_count > 0 AND is_public = 1"
            ).fetchone()
        finally:
            conn.close()

        return {
            "strategies": {
                "published_count": s_published["cnt"] if s_published else 0,
                "total_subscribers": s_total_subs["cnt"] if s_total_subs else 0,
                "total_clones": s_total_clones["cnt"] if s_total_clones else 0,
                "avg_rating": round(s_avg_rating["avg_r"], 2) if s_avg_rating else 0,
            },
            "factors": {
                "published_count": f_published["cnt"] if f_published else 0,
                "total_subscribers": f_total_subs["cnt"] if f_total_subs else 0,
                "total_clones": f_total_clones["cnt"] if f_total_clones else 0,
                "avg_rating": round(f_avg_rating["avg_r"], 2) if f_avg_rating else 0,
            },
        }
