"""Migrate existing file-based custom strategies into the strategy database.

Scans ``~/.vibe-trading/custom_strategies/`` (and the project-level
``./custom_strategies/`` directory) for ``.py`` files implementing
``SignalEngine``, validates each one, and imports it into ``strategies.db``
via :class:`StrategyService`.

The migration is **idempotent**: strategies already present in the DB
(matched by ``name_en`` == filename stem) are skipped.  A companion
``.meta.json`` file, if present, provides display metadata (name,
description, category, tags, parameters).

Usage
-----
::

    from src.strategy_manager.migration import migrate_custom_strategies

    report = migrate_custom_strategies(user_id="system")
    print(report.summary())

Or from the command line::

    python -m src.strategy_manager.migration
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.strategy_manager import db
from src.strategy_manager.service import StrategyService
from src.strategy_manager.validator import validate_strategy_source

logger = logging.getLogger(__name__)

MIGRATION_USER_ID = "_migrated"  # owner for strategies migrated from files


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class MigrationEntry:
    """Result of migrating a single strategy file."""

    filename: str
    strategy_id: str  # filename stem, e.g. "brick_reversal"
    status: str  # "created" / "skipped" / "failed"
    db_id: str | None = None  # DB uuid if created
    error: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class MigrationReport:
    """Aggregated result of a migration run."""

    entries: list[MigrationEntry] = field(default_factory=list)
    scanned: int = 0
    created: int = 0
    skipped: int = 0
    failed: int = 0

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        return (
            f"Migration complete: {self.scanned} scanned, "
            f"{self.created} created, {self.skipped} skipped, "
            f"{self.failed} failed"
        )

    def details(self) -> str:
        """Return a multi-line report with per-file details."""
        lines = [self.summary()]
        for e in self.entries:
            tag = {"created": "+", "skipped": "=", "failed": "!"}[e.status]
            line = f"  [{tag}] {e.filename}"
            if e.error:
                line += f"  ERROR: {e.error}"
            if e.warnings:
                line += f"  WARN: {'; '.join(e.warnings)}"
            lines.append(line)
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_custom_strategies_dirs() -> list[Path]:
    """Return the list of directories to scan for custom strategies.

    Mirrors the logic in ``templates._get_custom_strategies_dir()`` but
    returns *both* the user-level and project-level directories.
    """
    dirs: list[Path] = []

    # User-level: ~/.vibe-trading/custom_strategies/
    home_dir = Path.home() / ".vibe-trading" / "custom_strategies"
    if home_dir.exists():
        dirs.append(home_dir)

    # Project-level: ./custom_strategies/
    project_dir = Path.cwd() / "custom_strategies"
    if project_dir.exists() and project_dir not in dirs:
        dirs.append(project_dir)

    return dirs


def _read_meta_json(strategy_dir: Path, strategy_id: str) -> dict:
    """Read companion ``.meta.json`` file for a strategy, if it exists."""
    meta_file = strategy_dir / f"{strategy_id}.meta.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read meta for %s: %s", strategy_id, exc)
    return {}


def _find_existing_in_db(strategy_id: str) -> str | None:
    """Check if a strategy with ``name_en == strategy_id`` already exists.

    Returns the DB id if found, None otherwise.
    """
    all_strategies = StrategyService.list(limit=10000, include_code=False)
    for s in all_strategies:
        if s.name_en == strategy_id:
            return s.id
    return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def migrate_custom_strategies(
    *,
    user_id: str = MIGRATION_USER_ID,
    dirs: list[Path] | None = None,
    dry_run: bool = False,
) -> MigrationReport:
    """Migrate file-based custom strategies into the database.

    Args:
        user_id: Owner ID for migrated strategies.  Defaults to ``"_migrated"``.
        dirs: Directories to scan.  Defaults to user-level + project-level.
        dry_run: If True, validate and report but don't write to DB.

    Returns:
        A :class:`MigrationReport` with per-file results.
    """
    db.ensure_db()
    report = MigrationReport()

    if dirs is None:
        dirs = _get_custom_strategies_dirs()

    if not dirs:
        logger.info("No custom_strategies directories found — nothing to migrate")
        return report

    for strategy_dir in dirs:
        logger.info("Scanning %s", strategy_dir)

        for py_file in sorted(strategy_dir.glob("*.py")):
            if py_file.name.startswith("_") or py_file.name.startswith("."):
                continue

            strategy_id = py_file.stem  # e.g. "brick_reversal"
            report.scanned += 1

            entry = MigrationEntry(
                filename=py_file.name,
                strategy_id=strategy_id,
                status="failed",
            )

            # Read source code
            try:
                source = py_file.read_text(encoding="utf-8-sig")
            except OSError as exc:
                entry.error = f"Failed to read file: {exc}"
                report.entries.append(entry)
                report.failed += 1
                continue

            # Validate
            result = validate_strategy_source(source)
            if not result.valid:
                entry.error = "; ".join(result.errors[:3])
                report.entries.append(entry)
                report.failed += 1
                logger.warning("Validation failed for %s: %s", py_file, entry.error)
                continue

            if result.warnings:
                entry.warnings = result.warnings[:2]

            # Check if already migrated
            existing_id = _find_existing_in_db(strategy_id)
            if existing_id is not None:
                entry.status = "skipped"
                entry.db_id = existing_id
                report.entries.append(entry)
                report.skipped += 1
                logger.info("Skipping %s (already in DB as %s)", py_file.name, existing_id[:8])
                continue

            if dry_run:
                entry.status = "created"
                entry.db_id = "(dry-run)"
                report.entries.append(entry)
                report.created += 1
                continue

            # Read companion meta.json
            meta = _read_meta_json(strategy_dir, strategy_id)

            # Create in DB
            strategy, create_result = StrategyService.create(
                user_id=user_id,
                name=meta.get("name", strategy_id.replace("_", " ").title()),
                name_en=strategy_id,
                source_code=source,
                description=meta.get("description", result.metadata.get("description", "")),
                category=meta.get("category", "custom"),
                tags=meta.get("tags", []),
                meta={"markets": meta.get("markets", ["a_share"])},
                status="draft",
            )

            if strategy is not None:
                entry.status = "created"
                entry.db_id = strategy.id
                report.created += 1
                logger.info("Migrated %s -> DB id %s", py_file.name, strategy.id[:8])
            else:
                entry.error = "; ".join(create_result.errors[:3])
                report.failed += 1
                logger.warning("DB create failed for %s: %s", py_file.name, entry.error)

            report.entries.append(entry)

    logger.info(report.summary())
    return report


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = migrate_custom_strategies()
    print()
    print(report.details())
