"""SQLite connection management and schema for the strategy/factor store.

Database: ~/.vibe-trading/strategies.db
Connection pattern: per-call connections with WAL mode (same as usage/db.py).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_initialized = False

# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
_SCHEMA = """
-- ============================================================
-- 策略表
-- ============================================================
CREATE TABLE IF NOT EXISTS strategies (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    name             TEXT NOT NULL,
    name_en          TEXT DEFAULT '',
    description      TEXT DEFAULT '',
    category         TEXT DEFAULT 'custom',
    tags             TEXT DEFAULT '[]',
    source_code      TEXT NOT NULL,
    meta_json        TEXT DEFAULT '{}',
    version          INTEGER DEFAULT 1,
    status           TEXT DEFAULT 'draft',
    parent_id        TEXT,
    is_public        INTEGER DEFAULT 0,
    market_desc      TEXT DEFAULT '',
    subscriber_count INTEGER DEFAULT 0,
    clone_count      INTEGER DEFAULT 0,
    rating_avg       REAL DEFAULT 0,
    rating_count     INTEGER DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strategies_user ON strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status);
CREATE INDEX IF NOT EXISTS idx_strategies_public ON strategies(is_public) WHERE is_public = 1;
CREATE INDEX IF NOT EXISTS idx_strategies_category ON strategies(category);

-- ============================================================
-- 策略版本历史 (限量快照, 保留最近10个)
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_versions (
    id           TEXT PRIMARY KEY,
    strategy_id  TEXT NOT NULL,
    version      INTEGER NOT NULL,
    source_code  TEXT NOT NULL,
    meta_json    TEXT DEFAULT '{}',
    changelog    TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_strat_versions ON strategy_versions(strategy_id, version DESC);

-- ============================================================
-- 策略订阅 (用户订阅他人发布的策略, 跟随更新)
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_subscriptions (
    user_id       TEXT NOT NULL,
    strategy_id   TEXT NOT NULL,
    subscribed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, strategy_id),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
);

-- ============================================================
-- 策略评分
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_ratings (
    user_id     TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    rating      INTEGER NOT NULL,
    comment     TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, strategy_id),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
);

-- ============================================================
-- 因子表
-- ============================================================
CREATE TABLE IF NOT EXISTS factors (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    name             TEXT NOT NULL,
    name_en          TEXT DEFAULT '',
    description      TEXT DEFAULT '',
    category         TEXT DEFAULT 'custom',
    tags             TEXT DEFAULT '[]',
    source_code      TEXT NOT NULL,
    meta_json        TEXT DEFAULT '{}',
    version          INTEGER DEFAULT 1,
    status           TEXT DEFAULT 'draft',
    parent_id        TEXT,
    is_public        INTEGER DEFAULT 0,
    market_desc      TEXT DEFAULT '',
    subscriber_count INTEGER DEFAULT 0,
    clone_count      INTEGER DEFAULT 0,
    rating_avg       REAL DEFAULT 0,
    rating_count     INTEGER DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_factors_user ON factors(user_id);
CREATE INDEX IF NOT EXISTS idx_factors_public ON factors(is_public) WHERE is_public = 1;

CREATE TABLE IF NOT EXISTS factor_versions (
    id          TEXT PRIMARY KEY,
    factor_id   TEXT NOT NULL,
    version     INTEGER NOT NULL,
    source_code TEXT NOT NULL,
    meta_json   TEXT DEFAULT '{}',
    changelog   TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    FOREIGN KEY (factor_id) REFERENCES factors(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS factor_subscriptions (
    user_id       TEXT NOT NULL,
    factor_id     TEXT NOT NULL,
    subscribed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, factor_id),
    FOREIGN KEY (factor_id) REFERENCES factors(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS factor_ratings (
    user_id   TEXT NOT NULL,
    factor_id TEXT NOT NULL,
    rating    INTEGER NOT NULL,
    comment   TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, factor_id),
    FOREIGN KEY (factor_id) REFERENCES factors(id) ON DELETE CASCADE
);

-- ============================================================
-- 因子组合配置 (多因子策略)
-- ============================================================
CREATE TABLE IF NOT EXISTS factor_portfolios (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    config_json TEXT NOT NULL,
    status      TEXT DEFAULT 'draft',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_portfolios_user ON factor_portfolios(user_id);
"""


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def get_db_path() -> Path:
    """Return the path to ~/.vibe-trading/strategies.db."""
    from src.config.paths import get_data_dir
    return get_data_dir() / "strategies.db"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with WAL mode and foreign keys enabled.

    Each call creates a new connection.  WAL mode ensures concurrent reads
    do not block writes.  ``check_same_thread=False`` allows FastAPI async
    executors to share connections safely.
    """
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database schema (idempotent). Safe to call multiple times."""
    global _initialized
    if _initialized:
        return
    with _LOCK:
        if _initialized:
            return
        try:
            conn = get_connection()
            conn.executescript(_SCHEMA)
            conn.commit()
            conn.close()
            _initialized = True
            logger.info("Strategy database initialized at %s", get_db_path())
        except Exception:
            logger.exception("Failed to initialize strategy database")
            raise


def ensure_db() -> None:
    """Convenience wrapper — call before any DB operation."""
    if not _initialized:
        init_db()
