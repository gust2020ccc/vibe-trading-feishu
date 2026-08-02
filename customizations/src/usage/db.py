"""SQLite connection management and schema initialization for usage tracking."""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from src.config.paths import get_data_dir

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_initialized = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    name           TEXT DEFAULT '',
    email          TEXT DEFAULT '',
    password_hash  TEXT DEFAULT '',
    channel        TEXT DEFAULT 'feishu',
    role           TEXT DEFAULT 'user',
    status         TEXT DEFAULT 'active',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quotas (
    user_id                   TEXT PRIMARY KEY REFERENCES users(user_id),
    daily_token_limit         INTEGER NOT NULL DEFAULT 0,
    monthly_token_limit       INTEGER NOT NULL DEFAULT 0,
    concurrent_session_limit  INTEGER NOT NULL DEFAULT 0,
    rate_limit_per_minute     INTEGER NOT NULL DEFAULT 0,
    updated_at                TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_records (
    record_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    attempt_id    TEXT NOT NULL,
    channel       TEXT DEFAULT '',
    input_tokens  INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens  INTEGER DEFAULT 0,
    llm_calls     INTEGER DEFAULT 0,
    status        TEXT DEFAULT '',
    created_at    TEXT NOT NULL,
    date          TEXT NOT NULL,
    month         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_records(user_id, date);
CREATE INDEX IF NOT EXISTS idx_usage_month ON usage_records(user_id, month);

CREATE TABLE IF NOT EXISTS daily_aggregates (
    user_id        TEXT NOT NULL,
    date           TEXT NOT NULL,
    total_tokens   INTEGER DEFAULT 0,
    input_tokens   INTEGER DEFAULT 0,
    output_tokens  INTEGER DEFAULT 0,
    llm_calls      INTEGER DEFAULT 0,
    request_count  INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

CREATE TABLE IF NOT EXISTS monthly_aggregates (
    user_id        TEXT NOT NULL,
    month          TEXT NOT NULL,
    total_tokens   INTEGER DEFAULT 0,
    input_tokens   INTEGER DEFAULT 0,
    output_tokens  INTEGER DEFAULT 0,
    llm_calls      INTEGER DEFAULT 0,
    request_count  INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, month)
);
"""


def get_db_path() -> Path:
    """Return the path to ~/.vibe-trading/usage.db."""
    return get_data_dir() / "usage.db"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with WAL mode and foreign keys enabled."""
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

            # Migration: add email and password_hash columns if missing
            cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
            if "email" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
            if "password_hash" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT DEFAULT ''")
            # Create email index after ensuring column exists
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email != ''"
                )
            except Exception:
                pass

            conn.commit()
            conn.close()
            _initialized = True
            logger.info("Usage database initialized at %s", get_db_path())
        except Exception:
            logger.exception("Failed to initialize usage database")
            raise
