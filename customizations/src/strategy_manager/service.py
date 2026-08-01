"""CRUD + version management service for strategies and factors.

This is the single business-logic layer that sits between the API routes
and the SQLite database.  All operations go through here so that:

- Source code is always validated before persistence.
- Version snapshots are created automatically on update.
- Old versions are pruned to the last ``MAX_VERSIONS`` entries.
- JSON fields (``tags``, ``meta``) are serialised/deserialised consistently.
- Timestamps use ISO-8601 strings.

The module exposes two parallel hierarchies — ``StrategyService`` and
``FactorService`` — plus a ``MarketService`` stub for publish/clone/subscribe
(to be fully implemented in Sprint 4).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.strategy_manager import db
from src.strategy_manager.models import (
    Factor,
    FactorPortfolio,
    Strategy,
    StrategyVersion,
)
from src.strategy_manager.validator import (
    ValidationResult,
    validate_factor_source,
    validate_strategy_source,
)

logger = logging.getLogger(__name__)

MAX_VERSIONS = 10  # keep the most recent N version snapshots per item


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _now() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    """Generate a unique ID (UUID4 hex)."""
    return uuid.uuid4().hex


def _row_to_strategy(row) -> Strategy:
    """Convert a sqlite3.Row to a Strategy dataclass."""
    return Strategy(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        name_en=row["name_en"] or "",
        description=row["description"] or "",
        category=row["category"] or "custom",
        tags=json.loads(row["tags"]) if row["tags"] else [],
        source_code=row["source_code"],
        meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
        version=row["version"],
        status=row["status"] or "draft",
        parent_id=row["parent_id"],
        is_public=bool(row["is_public"]),
        market_desc=row["market_desc"] or "",
        subscriber_count=row["subscriber_count"] or 0,
        clone_count=row["clone_count"] or 0,
        rating_avg=row["rating_avg"] or 0.0,
        rating_count=row["rating_count"] or 0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_factor(row) -> Factor:
    """Convert a sqlite3.Row to a Factor dataclass."""
    return Factor(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        name_en=row["name_en"] or "",
        description=row["description"] or "",
        category=row["category"] or "custom",
        tags=json.loads(row["tags"]) if row["tags"] else [],
        source_code=row["source_code"],
        meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
        version=row["version"],
        status=row["status"] or "draft",
        parent_id=row["parent_id"],
        is_public=bool(row["is_public"]),
        market_desc=row["market_desc"] or "",
        subscriber_count=row["subscriber_count"] or 0,
        clone_count=row["clone_count"] or 0,
        rating_avg=row["rating_avg"] or 0.0,
        rating_count=row["rating_count"] or 0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_version(row) -> StrategyVersion:
    """Convert a sqlite3.Row to a StrategyVersion dataclass."""
    return StrategyVersion(
        id=row["id"],
        strategy_id=row["strategy_id"],
        version=row["version"],
        source_code=row["source_code"],
        meta=json.loads(row["meta_json"]) if row["meta_json"] else {},
        changelog=row["changelog"] or "",
        created_at=row["created_at"],
    )


def _save_version_snapshot(
    conn,
    table_versions: str,
    item_id_col: str,
    item_id: str,
    version: int,
    source_code: str,
    meta: dict[str, Any],
    changelog: str,
) -> None:
    """Insert a version snapshot and prune old entries beyond MAX_VERSIONS."""
    now = _now()
    conn.execute(
        f"""INSERT INTO {table_versions}
            (id, {item_id_col}, version, source_code, meta_json, changelog, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (_new_id(), item_id, version, source_code, json.dumps(meta, ensure_ascii=False),
         changelog, now),
    )
    # Prune: keep only the latest MAX_VERSIONS versions
    conn.execute(
        f"""DELETE FROM {table_versions}
            WHERE {item_id_col} = ?
              AND id NOT IN (
                SELECT id FROM {table_versions}
                WHERE {item_id_col} = ?
                ORDER BY version DESC
                LIMIT {MAX_VERSIONS}
              )""",
        (item_id, item_id),
    )


# --------------------------------------------------------------------------- #
# Strategy Service
# --------------------------------------------------------------------------- #
class StrategyService:
    """CRUD + version management for user strategies."""

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    @staticmethod
    def create(
        *,
        user_id: str,
        name: str,
        source_code: str,
        name_en: str = "",
        description: str = "",
        category: str = "custom",
        tags: list[str] | None = None,
        meta: dict[str, Any] | None = None,
        status: str = "draft",
        parent_id: str | None = None,
    ) -> tuple[Strategy | None, ValidationResult]:
        """Create a new strategy.

        Validates the source code first.  If validation fails, returns
        ``(None, result)``.  On success, persists to DB and returns
        ``(strategy, result)`` with extracted metadata.
        """
        db.ensure_db()

        # Validate
        result = validate_strategy_source(source_code)
        if not result.valid:
            return None, result

        # Merge extracted metadata with caller-provided meta
        merged_meta = dict(result.metadata)
        if meta:
            merged_meta.update(meta)

        now = _now()
        sid = _new_id()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        meta_json = json.dumps(merged_meta, ensure_ascii=False)

        conn = db.get_connection()
        try:
            conn.execute(
                """INSERT INTO strategies
                   (id, user_id, name, name_en, description, category, tags,
                    source_code, meta_json, version, status, parent_id,
                    is_public, market_desc, subscriber_count, clone_count,
                    rating_avg, rating_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0, '', 0, 0, 0, 0, ?, ?)""",
                (sid, user_id, name, name_en, description, category, tags_json,
                 source_code, meta_json, status, parent_id, now, now),
            )
            # Save initial version snapshot
            _save_version_snapshot(
                conn, "strategy_versions", "strategy_id",
                sid, 1, source_code, merged_meta, "Initial version",
            )
            conn.commit()
        finally:
            conn.close()

        strategy = StrategyService.get(sid)
        logger.info("Created strategy %s (%s) for user %s", sid, name, user_id)
        return strategy, result

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    @staticmethod
    def get(strategy_id: str, include_code: bool = False) -> Strategy | None:
        """Return a single strategy by ID, or None if not found."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM strategies WHERE id = ?", (strategy_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        s = _row_to_strategy(row)
        if not include_code:
            s.source_code = ""
        return s

    @staticmethod
    def get_source(strategy_id: str) -> str | None:
        """Return only the source code for a strategy, or None."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            row = conn.execute(
                "SELECT source_code FROM strategies WHERE id = ?", (strategy_id,)
            ).fetchone()
        finally:
            conn.close()
        return row["source_code"] if row else None

    @staticmethod
    def list(
        *,
        user_id: str | None = None,
        status: str | None = None,
        category: str | None = None,
        is_public: bool | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        include_code: bool = False,
    ) -> list[Strategy]:
        """List strategies with optional filters.

        Args:
            user_id: Filter by owner.
            status: Filter by status (draft/testing/published/archived).
            category: Filter by category.
            is_public: Filter by public visibility.
            search: Case-insensitive substring match on name/description.
            limit: Max results.
            offset: Pagination offset.
            include_code: Include source_code in results (default: excluded).
        """
        db.ensure_db()
        clauses: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if is_public is not None:
            clauses.append("is_public = ?")
            params.append(1 if is_public else 0)
        if search:
            clauses.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"SELECT * FROM strategies{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = db.get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        results = [_row_to_strategy(r) for r in rows]
        if not include_code:
            for s in results:
                s.source_code = ""
        return results

    @staticmethod
    def count(*, user_id: str | None = None, status: str | None = None) -> int:
        """Count strategies matching the given filters."""
        db.ensure_db()
        clauses: list[str] = []
        params: list[Any] = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        conn = db.get_connection()
        try:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM strategies{where}", params).fetchone()
        finally:
            conn.close()
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    @staticmethod
    def update(
        strategy_id: str,
        *,
        name: str | None = None,
        source_code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        meta: dict[str, Any] | None = None,
        status: str | None = None,
        changelog: str = "",
    ) -> tuple[Strategy | None, ValidationResult]:
        """Update a strategy.

        If ``source_code`` is provided, it is validated first.  On successful
        update, a new version snapshot is saved and ``version`` is incremented.

        Returns ``(updated_strategy, validation_result)``.  If validation
        fails, returns ``(original_strategy_unchanged, result)``.
        """
        db.ensure_db()
        existing = StrategyService.get(strategy_id, include_code=True)
        if existing is None:
            return None, ValidationResult(valid=False, errors=["Strategy not found"])

        result = ValidationResult(valid=True)
        new_version = existing.version
        merged_meta = existing.meta

        if source_code is not None and source_code != existing.source_code:
            result = validate_strategy_source(source_code)
            if not result.valid:
                return existing, result
            new_version = existing.version + 1
            # Merge extracted metadata
            merged_meta = dict(result.metadata)
            if meta:
                merged_meta.update(meta)

        # Build UPDATE query dynamically
        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if source_code is not None:
            sets.append("source_code = ?")
            params.append(source_code)
            sets.append("version = ?")
            params.append(new_version)
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if category is not None:
            sets.append("category = ?")
            params.append(category)
        if tags is not None:
            sets.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if meta is not None and source_code is None:
            # Only update meta if source_code wasn't changed (source change already merges)
            merged_meta = dict(existing.meta)
            merged_meta.update(meta)
        if source_code is not None or meta is not None:
            sets.append("meta_json = ?")
            params.append(json.dumps(merged_meta, ensure_ascii=False))
        if status is not None:
            sets.append("status = ?")
            params.append(status)

        if not sets:
            return existing, result

        sets.append("updated_at = ?")
        params.append(_now())
        params.append(strategy_id)

        conn = db.get_connection()
        try:
            conn.execute(
                f"UPDATE strategies SET {', '.join(sets)} WHERE id = ?", params
            )
            # Save version snapshot if code changed
            if source_code is not None and new_version > existing.version:
                _save_version_snapshot(
                    conn, "strategy_versions", "strategy_id",
                    strategy_id, new_version,
                    source_code, merged_meta,
                    changelog or f"Version {new_version}",
                )
            conn.commit()
        finally:
            conn.close()

        logger.info("Updated strategy %s to version %d", strategy_id, new_version)
        return StrategyService.get(strategy_id), result

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    @staticmethod
    def delete(strategy_id: str) -> bool:
        """Delete a strategy and all its versions. Returns True if deleted."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        finally:
            conn.close()
        if deleted:
            logger.info("Deleted strategy %s", strategy_id)
        return deleted

    # ------------------------------------------------------------------ #
    # Version management
    # ------------------------------------------------------------------ #
    @staticmethod
    def list_versions(strategy_id: str, include_code: bool = False) -> list[StrategyVersion]:
        """List version history for a strategy (newest first)."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            rows = conn.execute(
                """SELECT * FROM strategy_versions
                   WHERE strategy_id = ?
                   ORDER BY version DESC""",
                (strategy_id,),
            ).fetchall()
        finally:
            conn.close()
        versions = [_row_to_version(r) for r in rows]
        if not include_code:
            for v in versions:
                v.source_code = ""
        return versions

    @staticmethod
    def get_version(strategy_id: str, version: int) -> StrategyVersion | None:
        """Return a specific version snapshot, or None."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            row = conn.execute(
                """SELECT * FROM strategy_versions
                   WHERE strategy_id = ? AND version = ?""",
                (strategy_id, version),
            ).fetchone()
        finally:
            conn.close()
        return _row_to_version(row) if row else None

    @staticmethod
    def rollback(strategy_id: str, version: int) -> tuple[Strategy | None, ValidationResult]:
        """Restore a strategy to a previous version.

        Creates a *new* version (version+1) with the old code, so the
        history is never lost.
        """
        db.ensure_db()
        snapshot = StrategyService.get_version(strategy_id, version)
        if snapshot is None:
            return None, ValidationResult(valid=False, errors=["Version not found"])

        return StrategyService.update(
            strategy_id,
            source_code=snapshot.source_code,
            meta=snapshot.meta,
            changelog=f"Rollback to version {version}",
        )


# --------------------------------------------------------------------------- #
# Factor Service (parallel to StrategyService)
# --------------------------------------------------------------------------- #
class FactorService:
    """CRUD + version management for user factors."""

    @staticmethod
    def create(
        *,
        user_id: str,
        name: str,
        source_code: str,
        name_en: str = "",
        description: str = "",
        category: str = "custom",
        tags: list[str] | None = None,
        meta: dict[str, Any] | None = None,
        status: str = "draft",
        parent_id: str | None = None,
    ) -> tuple[Factor | None, ValidationResult]:
        """Create a new factor (validates source first)."""
        db.ensure_db()

        result = validate_factor_source(source_code)
        if not result.valid:
            return None, result

        merged_meta = dict(result.metadata)
        if meta:
            merged_meta.update(meta)

        now = _now()
        fid = _new_id()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        meta_json = json.dumps(merged_meta, ensure_ascii=False)

        conn = db.get_connection()
        try:
            conn.execute(
                """INSERT INTO factors
                   (id, user_id, name, name_en, description, category, tags,
                    source_code, meta_json, version, status, parent_id,
                    is_public, market_desc, subscriber_count, clone_count,
                    rating_avg, rating_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0, '', 0, 0, 0, 0, ?, ?)""",
                (fid, user_id, name, name_en, description, category, tags_json,
                 source_code, meta_json, status, parent_id, now, now),
            )
            _save_version_snapshot(
                conn, "factor_versions", "factor_id",
                fid, 1, source_code, merged_meta, "Initial version",
            )
            conn.commit()
        finally:
            conn.close()

        factor = FactorService.get(fid)
        logger.info("Created factor %s (%s) for user %s", fid, name, user_id)
        return factor, result

    @staticmethod
    def get(factor_id: str, include_code: bool = False) -> Factor | None:
        """Return a single factor by ID, or None."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM factors WHERE id = ?", (factor_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        f = _row_to_factor(row)
        if not include_code:
            f.source_code = ""
        return f

    @staticmethod
    def get_source(factor_id: str) -> str | None:
        """Return only the source code for a factor, or None."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            row = conn.execute(
                "SELECT source_code FROM factors WHERE id = ?", (factor_id,)
            ).fetchone()
        finally:
            conn.close()
        return row["source_code"] if row else None

    @staticmethod
    def list(
        *,
        user_id: str | None = None,
        status: str | None = None,
        category: str | None = None,
        is_public: bool | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        include_code: bool = False,
    ) -> list[Factor]:
        """List factors with optional filters."""
        db.ensure_db()
        clauses: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if is_public is not None:
            clauses.append("is_public = ?")
            params.append(1 if is_public else 0)
        if search:
            clauses.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"SELECT * FROM factors{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = db.get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        results = [_row_to_factor(r) for r in rows]
        if not include_code:
            for f in results:
                f.source_code = ""
        return results

    @staticmethod
    def update(
        factor_id: str,
        *,
        name: str | None = None,
        source_code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        meta: dict[str, Any] | None = None,
        status: str | None = None,
        changelog: str = "",
    ) -> tuple[Factor | None, ValidationResult]:
        """Update a factor. Validates source code if changed."""
        db.ensure_db()
        existing = FactorService.get(factor_id, include_code=True)
        if existing is None:
            return None, ValidationResult(valid=False, errors=["Factor not found"])

        result = ValidationResult(valid=True)
        new_version = existing.version
        merged_meta = existing.meta

        if source_code is not None and source_code != existing.source_code:
            result = validate_factor_source(source_code)
            if not result.valid:
                return existing, result
            new_version = existing.version + 1
            merged_meta = dict(result.metadata)
            if meta:
                merged_meta.update(meta)

        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if source_code is not None:
            sets.append("source_code = ?")
            params.append(source_code)
            sets.append("version = ?")
            params.append(new_version)
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if category is not None:
            sets.append("category = ?")
            params.append(category)
        if tags is not None:
            sets.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if meta is not None and source_code is None:
            merged_meta = dict(existing.meta)
            merged_meta.update(meta)
        if source_code is not None or meta is not None:
            sets.append("meta_json = ?")
            params.append(json.dumps(merged_meta, ensure_ascii=False))
        if status is not None:
            sets.append("status = ?")
            params.append(status)

        if not sets:
            return existing, result

        sets.append("updated_at = ?")
        params.append(_now())
        params.append(factor_id)

        conn = db.get_connection()
        try:
            conn.execute(
                f"UPDATE factors SET {', '.join(sets)} WHERE id = ?", params
            )
            if source_code is not None and new_version > existing.version:
                _save_version_snapshot(
                    conn, "factor_versions", "factor_id",
                    factor_id, new_version,
                    source_code, merged_meta,
                    changelog or f"Version {new_version}",
                )
            conn.commit()
        finally:
            conn.close()

        logger.info("Updated factor %s to version %d", factor_id, new_version)
        return FactorService.get(factor_id), result

    @staticmethod
    def delete(factor_id: str) -> bool:
        """Delete a factor and all its versions."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM factors WHERE id = ?", (factor_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        finally:
            conn.close()
        if deleted:
            logger.info("Deleted factor %s", factor_id)
        return deleted


# --------------------------------------------------------------------------- #
# Factor Portfolio Service
# --------------------------------------------------------------------------- #
class PortfolioService:
    """CRUD for multi-factor combination configurations."""

    @staticmethod
    def create(
        *,
        user_id: str,
        name: str,
        config: dict[str, Any],
        description: str = "",
        status: str = "draft",
    ) -> FactorPortfolio:
        """Create a new factor portfolio configuration."""
        db.ensure_db()
        now = _now()
        pid = _new_id()
        config_json = json.dumps(config, ensure_ascii=False)

        conn = db.get_connection()
        try:
            conn.execute(
                """INSERT INTO factor_portfolios
                   (id, user_id, name, description, config_json, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, user_id, name, description, config_json, status, now, now),
            )
            conn.commit()
        finally:
            conn.close()

        return PortfolioService.get(pid)  # type: ignore[return-value]

    @staticmethod
    def get(portfolio_id: str) -> FactorPortfolio | None:
        """Return a single portfolio, or None."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM factor_portfolios WHERE id = ?", (portfolio_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return FactorPortfolio(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            description=row["description"] or "",
            config=json.loads(row["config_json"]) if row["config_json"] else {},
            status=row["status"] or "draft",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def list(*, user_id: str | None = None, limit: int = 100, offset: int = 0) -> list[FactorPortfolio]:
        """List portfolios with optional user filter."""
        db.ensure_db()
        if user_id is not None:
            query = "SELECT * FROM factor_portfolios WHERE user_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params: list[Any] = [user_id, limit, offset]
        else:
            query = f"SELECT * FROM factor_portfolios ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params = [limit, offset]

        conn = db.get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        return [
            FactorPortfolio(
                id=r["id"],
                user_id=r["user_id"],
                name=r["name"],
                description=r["description"] or "",
                config=json.loads(r["config_json"]) if r["config_json"] else {},
                status=r["status"] or "draft",
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    @staticmethod
    def update(
        portfolio_id: str,
        *,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> FactorPortfolio | None:
        """Update a portfolio configuration."""
        db.ensure_db()
        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if config is not None:
            sets.append("config_json = ?")
            params.append(json.dumps(config, ensure_ascii=False))
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if status is not None:
            sets.append("status = ?")
            params.append(status)

        if not sets:
            return PortfolioService.get(portfolio_id)

        sets.append("updated_at = ?")
        params.append(_now())
        params.append(portfolio_id)

        conn = db.get_connection()
        try:
            conn.execute(
                f"UPDATE factor_portfolios SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
        finally:
            conn.close()

        return PortfolioService.get(portfolio_id)

    @staticmethod
    def delete(portfolio_id: str) -> bool:
        """Delete a portfolio."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM factor_portfolios WHERE id = ?", (portfolio_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Market Service (stubs — fully implemented in Sprint 4)
# --------------------------------------------------------------------------- #
class MarketService:
    """Publish / clone / subscribe / rate — strategy & factor marketplace.

    Sprint 1 implements only the publish + rate operations; clone and
    subscribe are stubs that will be completed in Sprint 4.
    """

    # ------------------------------------------------------------------ #
    # Publish / unpublish
    # ------------------------------------------------------------------ #
    @staticmethod
    def publish_strategy(strategy_id: str) -> Strategy | None:
        """Change a strategy's status to 'published' and set is_public."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            conn.execute(
                "UPDATE strategies SET status = 'published', is_public = 1, updated_at = ? WHERE id = ?",
                (_now(), strategy_id),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info("Published strategy %s", strategy_id)
        return StrategyService.get(strategy_id)

    @staticmethod
    def archive_strategy(strategy_id: str) -> Strategy | None:
        """Change a strategy's status to 'archived'."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            conn.execute(
                "UPDATE strategies SET status = 'archived', is_public = 0, updated_at = ? WHERE id = ?",
                (_now(), strategy_id),
            )
            conn.commit()
        finally:
            conn.close()
        return StrategyService.get(strategy_id)

    @staticmethod
    def publish_factor(factor_id: str) -> Factor | None:
        """Change a factor's status to 'published'."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            conn.execute(
                "UPDATE factors SET status = 'published', is_public = 1, updated_at = ? WHERE id = ?",
                (_now(), factor_id),
            )
            conn.commit()
        finally:
            conn.close()
        return FactorService.get(factor_id)

    # ------------------------------------------------------------------ #
    # Clone (independent fork)
    # ------------------------------------------------------------------ #
    @staticmethod
    def clone_strategy(strategy_id: str, user_id: str) -> tuple[Strategy | None, ValidationResult]:
        """Clone a published strategy into the caller's workspace.

        The clone is an independent copy with ``parent_id`` set to the
        original strategy.  The original's ``clone_count`` is incremented.
        """
        db.ensure_db()
        original = StrategyService.get(strategy_id, include_code=True)
        if original is None:
            return None, ValidationResult(valid=False, errors=["Strategy not found"])
        if not original.is_public:
            return None, ValidationResult(valid=False, errors=["Strategy is not public"])

        clone, result = StrategyService.create(
            user_id=user_id,
            name=f"{original.name} (clone)",
            source_code=original.source_code,
            name_en=original.name_en,
            description=original.description,
            category=original.category,
            tags=original.tags,
            meta=original.meta,
            status="draft",
            parent_id=original.id,
        )

        if clone is not None:
            conn = db.get_connection()
            try:
                conn.execute(
                    "UPDATE strategies SET clone_count = clone_count + 1 WHERE id = ?",
                    (original.id,),
                )
                conn.commit()
            finally:
                conn.close()

        return clone, result

    @staticmethod
    def clone_factor(factor_id: str, user_id: str) -> tuple[Factor | None, ValidationResult]:
        """Clone a published factor into the caller's workspace."""
        db.ensure_db()
        original = FactorService.get(factor_id, include_code=True)
        if original is None:
            return None, ValidationResult(valid=False, errors=["Factor not found"])
        if not original.is_public:
            return None, ValidationResult(valid=False, errors=["Factor is not public"])

        clone, result = FactorService.create(
            user_id=user_id,
            name=f"{original.name} (clone)",
            source_code=original.source_code,
            name_en=original.name_en,
            description=original.description,
            category=original.category,
            tags=original.tags,
            meta=original.meta,
            status="draft",
            parent_id=original.id,
        )

        if clone is not None:
            conn = db.get_connection()
            try:
                conn.execute(
                    "UPDATE factors SET clone_count = clone_count + 1 WHERE id = ?",
                    (original.id,),
                )
                conn.commit()
            finally:
                conn.close()

        return clone, result

    # ------------------------------------------------------------------ #
    # Subscribe (follow updates)
    # ------------------------------------------------------------------ #
    @staticmethod
    def subscribe_strategy(strategy_id: str, user_id: str) -> bool:
        """Subscribe a user to a published strategy's updates."""
        db.ensure_db()
        now = _now()
        conn = db.get_connection()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO strategy_subscriptions (user_id, strategy_id, subscribed_at)
                   VALUES (?, ?, ?)""",
                (user_id, strategy_id, now),
            )
            conn.execute(
                "UPDATE strategies SET subscriber_count = subscriber_count + 1 WHERE id = ?",
                (strategy_id,),
            )
            conn.commit()
            return True
        except Exception:  # noqa: BLE001
            logger.exception("Failed to subscribe user %s to strategy %s", user_id, strategy_id)
            return False
        finally:
            conn.close()

    @staticmethod
    def unsubscribe_strategy(strategy_id: str, user_id: str) -> bool:
        """Unsubscribe a user from a strategy."""
        db.ensure_db()
        conn = db.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM strategy_subscriptions WHERE user_id = ? AND strategy_id = ?",
                (user_id, strategy_id),
            )
            if cursor.rowcount > 0:
                conn.execute(
                    "UPDATE strategies SET subscriber_count = MAX(0, subscriber_count - 1) WHERE id = ?",
                    (strategy_id,),
                )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Ratings
    # ------------------------------------------------------------------ #
    @staticmethod
    def rate_strategy(strategy_id: str, user_id: str, rating: int, comment: str = "") -> bool:
        """Rate a strategy (1-5 stars). Upserts the user's existing rating."""
        db.ensure_db()
        if not 1 <= rating <= 5:
            return False
        now = _now()
        conn = db.get_connection()
        try:
            # Upsert rating
            conn.execute(
                """INSERT INTO strategy_ratings (user_id, strategy_id, rating, comment, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, strategy_id)
                   DO UPDATE SET rating = excluded.rating, comment = excluded.comment, created_at = excluded.created_at""",
                (user_id, strategy_id, rating, comment, now),
            )
            # Recalculate aggregate
            row = conn.execute(
                """SELECT AVG(rating) as avg_r, COUNT(*) as cnt
                   FROM strategy_ratings WHERE strategy_id = ?""",
                (strategy_id,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE strategies SET rating_avg = ?, rating_count = ? WHERE id = ?",
                    (row["avg_r"] or 0.0, row["cnt"], strategy_id),
                )
            conn.commit()
            return True
        except Exception:  # noqa: BLE001
            logger.exception("Failed to rate strategy %s", strategy_id)
            return False
        finally:
            conn.close()

    @staticmethod
    def rate_factor(factor_id: str, user_id: str, rating: int, comment: str = "") -> bool:
        """Rate a factor (1-5 stars). Upserts the user's existing rating."""
        db.ensure_db()
        if not 1 <= rating <= 5:
            return False
        now = _now()
        conn = db.get_connection()
        try:
            conn.execute(
                """INSERT INTO factor_ratings (user_id, factor_id, rating, comment, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, factor_id)
                   DO UPDATE SET rating = excluded.rating, comment = excluded.comment, created_at = excluded.created_at""",
                (user_id, factor_id, rating, comment, now),
            )
            row = conn.execute(
                """SELECT AVG(rating) as avg_r, COUNT(*) as cnt
                   FROM factor_ratings WHERE factor_id = ?""",
                (factor_id,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE factors SET rating_avg = ?, rating_count = ? WHERE id = ?",
                    (row["avg_r"] or 0.0, row["cnt"], factor_id),
                )
            conn.commit()
            return True
        except Exception:  # noqa: BLE001
            logger.exception("Failed to rate factor %s", factor_id)
            return False
        finally:
            conn.close()
