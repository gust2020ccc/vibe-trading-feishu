"""UsageQuotaService: core service for quota checking, usage recording, and admin CRUD.

This service is designed as a singleton, initialized once and shared across
the channel runtime (for quota checks) and the session service (for usage
recording via callback).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.usage.db import get_connection, init_db
from src.usage.models import Quota, QuotaCheckResult, UsageSummary, User
from src.usage.rate_limiter import ConcurrencyTracker, RateLimiter

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _this_month() -> str:
    return datetime.now().strftime("%Y-%m")


class UsageQuotaService:
    """Singleton service for usage tracking and quota enforcement."""

    def __init__(self) -> None:
        init_db()
        self._rate_limiter = RateLimiter()
        self._concurrency = ConcurrencyTracker()
        self._write_lock = threading.Lock()

        # Default quotas (overridable via env vars)
        self._default_daily_token = int(os.environ.get("USAGE_DEFAULT_DAILY_TOKEN", "0"))
        self._default_monthly_token = int(os.environ.get("USAGE_DEFAULT_MONTHLY_TOKEN", "0"))
        self._default_concurrent = int(os.environ.get("USAGE_DEFAULT_CONCURRENT", "3"))
        self._default_rpm = int(os.environ.get("USAGE_DEFAULT_RPM", "20"))

    # ================================================================
    # Quota checking (called from ChannelRuntime._handle_inbound)
    # ================================================================

    def check_and_acquire(self, sender_id: str, channel: str) -> QuotaCheckResult:
        """Check all quota dimensions and atomically acquire concurrency slot.

        Check order: user status → rate limit → concurrency → daily token → monthly token.
        If any check fails, concurrency slot is NOT incremented.

        Args:
            sender_id: The user's channel ID (e.g. Feishu open_id).
            channel: The channel name (e.g. "feishu").

        Returns:
            QuotaCheckResult with allowed=True if all checks pass.
        """
        try:
            user = self.get_or_create_user(sender_id, channel)

            # 1. User status check
            if user.status == "disabled":
                return QuotaCheckResult(
                    allowed=False,
                    reason="disabled",
                    deny_message="您的账号已被停用，请联系管理员。",
                )

            quota = self.get_quota(sender_id)

            # 2. Rate limit check (in-memory)
            if quota.rate_limit_per_minute > 0:
                if not self._rate_limiter.acquire(sender_id, quota.rate_limit_per_minute):
                    return QuotaCheckResult(
                        allowed=False,
                        reason="rate_limited",
                        deny_message=f"请求过于频繁，请稍后再试（每分钟限 {quota.rate_limit_per_minute} 次）。",
                    )

            # 3. Concurrency check (in-memory, atomic check+increment)
            if quota.concurrent_session_limit > 0:
                if not self._concurrency.try_acquire(sender_id, quota.concurrent_session_limit):
                    current = self._concurrency.current(sender_id)
                    return QuotaCheckResult(
                        allowed=False,
                        reason="concurrent_exceeded",
                        deny_message=f"您已有 {current} 个进行中的会话，请等待当前任务完成后再试。",
                    )

            # 4. Daily token quota check (DB)
            if quota.daily_token_limit > 0:
                today_used = self._get_daily_tokens(sender_id, _today())
                if today_used >= quota.daily_token_limit:
                    return QuotaCheckResult(
                        allowed=False,
                        reason="daily_exceeded",
                        deny_message=(
                            f"今日 Token 用量已达上限（{today_used:,}/{quota.daily_token_limit:,}），"
                            "请明日再试。"
                        ),
                        current_usage={"today_tokens": today_used, "daily_limit": quota.daily_token_limit},
                    )

            # 5. Monthly token quota check (DB)
            if quota.monthly_token_limit > 0:
                month_used = self._get_monthly_tokens(sender_id, _this_month())
                if month_used >= quota.monthly_token_limit:
                    return QuotaCheckResult(
                        allowed=False,
                        reason="monthly_exceeded",
                        deny_message=(
                            f"本月 Token 用量已达上限（{month_used:,}/{quota.monthly_token_limit:,}），"
                            "请下月再试。"
                        ),
                        current_usage={"month_tokens": month_used, "monthly_limit": quota.monthly_token_limit},
                    )

            return QuotaCheckResult(allowed=True)

        except Exception:
            logger.exception("Error in check_and_acquire for %s", sender_id)
            # Fail open: allow the request if quota system has an error
            return QuotaCheckResult(allowed=True)

    def release_concurrency(self, sender_id: str) -> None:
        """Release a concurrency slot (called after attempt completes)."""
        self._concurrency.release(sender_id)

    # ================================================================
    # Usage recording (called from SessionService._run_attempt via callback)
    # ================================================================

    def record_attempt_usage(
        self,
        sender_id: str = "",
        channel: str = "",
        session_id: str = "",
        attempt_id: str = "",
        run_dir: str = "",
        status: str = "",
        **kwargs: Any,
    ) -> None:
        """Read token usage from run_dir/llm_usage.json and persist to DB.

        Also releases the concurrency slot to ensure it's always freed.
        """
        try:
            # Always release concurrency, even if recording fails
            if sender_id:
                self.release_concurrency(sender_id)

            if not sender_id:
                return

            # Read token totals from llm_usage.json
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            llm_calls = 0

            if run_dir:
                usage_path = Path(run_dir) / "llm_usage.json"
                if usage_path.exists():
                    try:
                        data = json.loads(usage_path.read_text(encoding="utf-8"))
                        totals = data.get("totals", {})
                        input_tokens = int(totals.get("input_tokens", 0))
                        output_tokens = int(totals.get("output_tokens", 0))
                        total_tokens = int(totals.get("total_tokens", 0))
                        llm_calls = int(totals.get("calls", 0))
                    except (json.JSONDecodeError, OSError):
                        logger.warning("Failed to read llm_usage.json at %s", usage_path)

            # Ensure user exists
            self.get_or_create_user(sender_id, channel or "feishu")

            now = _now_iso()
            today = _today()
            month = _this_month()

            with self._write_lock:
                conn = get_connection()
                try:
                    # Insert usage record
                    conn.execute(
                        """INSERT INTO usage_records
                           (user_id, session_id, attempt_id, channel,
                            input_tokens, output_tokens, total_tokens,
                            llm_calls, status, created_at, date, month)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (sender_id, session_id, attempt_id, channel,
                         input_tokens, output_tokens, total_tokens,
                         llm_calls, status, now, today, month),
                    )

                    # Upsert daily aggregate
                    conn.execute(
                        """INSERT INTO daily_aggregates
                           (user_id, date, total_tokens, input_tokens, output_tokens,
                            llm_calls, request_count)
                           VALUES (?, ?, ?, ?, ?, ?, 1)
                           ON CONFLICT(user_id, date) DO UPDATE SET
                            total_tokens = total_tokens + excluded.total_tokens,
                            input_tokens = input_tokens + excluded.input_tokens,
                            output_tokens = output_tokens + excluded.output_tokens,
                            llm_calls = llm_calls + excluded.llm_calls,
                            request_count = request_count + 1""",
                        (sender_id, today, total_tokens, input_tokens, output_tokens, llm_calls),
                    )

                    # Upsert monthly aggregate
                    conn.execute(
                        """INSERT INTO monthly_aggregates
                           (user_id, month, total_tokens, input_tokens, output_tokens,
                            llm_calls, request_count)
                           VALUES (?, ?, ?, ?, ?, ?, 1)
                           ON CONFLICT(user_id, month) DO UPDATE SET
                            total_tokens = total_tokens + excluded.total_tokens,
                            input_tokens = input_tokens + excluded.input_tokens,
                            output_tokens = output_tokens + excluded.output_tokens,
                            llm_calls = llm_calls + excluded.llm_calls,
                            request_count = request_count + 1""",
                        (sender_id, month, total_tokens, input_tokens, output_tokens, llm_calls),
                    )

                    conn.commit()
                finally:
                    conn.close()

            logger.info(
                "Recorded usage for %s: tokens=%d, calls=%d, status=%s",
                sender_id, total_tokens, llm_calls, status,
            )

        except Exception:
            logger.exception("Error in record_attempt_usage")

    # ================================================================
    # User CRUD
    # ================================================================

    def get_or_create_user(self, user_id: str, channel: str = "feishu", name: str = "") -> User:
        """Get a user, creating with defaults if not exists."""
        existing = self.get_user(user_id)
        if existing is not None:
            return existing

        now = _now_iso()
        with self._write_lock:
            conn = get_connection()
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO users
                       (user_id, name, channel, role, status, created_at, updated_at)
                       VALUES (?, ?, ?, 'user', 'active', ?, ?)""",
                    (user_id, name, channel, now, now),
                )
                # Create default quota row
                conn.execute(
                    """INSERT OR IGNORE INTO quotas
                       (user_id, daily_token_limit, monthly_token_limit,
                        concurrent_session_limit, rate_limit_per_minute, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, self._default_daily_token, self._default_monthly_token,
                     self._default_concurrent, self._default_rpm, now),
                )
                conn.commit()
            finally:
                conn.close()

        return self.get_user(user_id) or User(
            user_id=user_id, channel=channel, created_at=now, updated_at=now
        )

    def get_user(self, user_id: str) -> User | None:
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                return None
            return User(**dict(row))
        finally:
            conn.close()

    def list_users(self) -> list[User]:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
            return [User(**dict(r)) for r in rows]
        finally:
            conn.close()

    def update_user(self, user_id: str, **fields: Any) -> User | None:
        """Update user fields. Allowed keys: name, role, status."""
        allowed = {"name", "role", "status"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get_user(user_id)

        updates["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [user_id]

        with self._write_lock:
            conn = get_connection()
            try:
                conn.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", params)
                conn.commit()
            finally:
                conn.close()

        return self.get_user(user_id)

    def delete_user(self, user_id: str) -> bool:
        with self._write_lock:
            conn = get_connection()
            try:
                # Delete child rows first to satisfy FK constraints
                conn.execute("DELETE FROM quotas WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM usage_records WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM daily_aggregates WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM monthly_aggregates WHERE user_id = ?", (user_id,))
                cur = conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    # ================================================================
    # Quota CRUD
    # ================================================================

    def get_quota(self, user_id: str) -> Quota:
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM quotas WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                # Return default quota
                return Quota(
                    user_id=user_id,
                    daily_token_limit=self._default_daily_token,
                    monthly_token_limit=self._default_monthly_token,
                    concurrent_session_limit=self._default_concurrent,
                    rate_limit_per_minute=self._default_rpm,
                )
            d = dict(row)
            d.pop("updated_at", None)  # Not in Quota dataclass
            return Quota(**d)
        finally:
            conn.close()

    def set_quota(self, user_id: str, **fields: Any) -> Quota:
        """Set or update quota fields. Allowed keys: daily_token_limit,
        monthly_token_limit, concurrent_session_limit, rate_limit_per_minute.
        """
        allowed = {"daily_token_limit", "monthly_token_limit",
                    "concurrent_session_limit", "rate_limit_per_minute"}
        updates = {k: int(v) for k, v in fields.items() if k in allowed and v is not None}

        # Ensure user exists
        self.get_or_create_user(user_id)

        now = _now_iso()
        with self._write_lock:
            conn = get_connection()
            try:
                # Upsert quota
                existing = conn.execute(
                    "SELECT user_id FROM quotas WHERE user_id = ?", (user_id,)
                ).fetchone()

                if existing is None:
                    # Insert with defaults, then update
                    conn.execute(
                        """INSERT INTO quotas
                           (user_id, daily_token_limit, monthly_token_limit,
                            concurrent_session_limit, rate_limit_per_minute, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (user_id, self._default_daily_token, self._default_monthly_token,
                         self._default_concurrent, self._default_rpm, now),
                    )

                if updates:
                    updates["updated_at"] = now
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    params = list(updates.values()) + [user_id]
                    conn.execute(f"UPDATE quotas SET {set_clause} WHERE user_id = ?", params)

                conn.commit()
            finally:
                conn.close()

        return self.get_quota(user_id)

    # ================================================================
    # Usage queries
    # ================================================================

    def _get_daily_tokens(self, user_id: str, date: str) -> int:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT total_tokens FROM daily_aggregates WHERE user_id = ? AND date = ?",
                (user_id, date),
            ).fetchone()
            return row["total_tokens"] if row else 0
        finally:
            conn.close()

    def _get_monthly_tokens(self, user_id: str, month: str) -> int:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT total_tokens FROM monthly_aggregates WHERE user_id = ? AND month = ?",
                (user_id, month),
            ).fetchone()
            return row["total_tokens"] if row else 0
        finally:
            conn.close()

    def get_usage_summary(self, user_id: str) -> UsageSummary:
        """Get aggregated usage summary for a user."""
        today = _today()
        month = _this_month()
        conn = get_connection()
        try:
            d_row = conn.execute(
                "SELECT * FROM daily_aggregates WHERE user_id = ? AND date = ?",
                (user_id, today),
            ).fetchone()
            m_row = conn.execute(
                "SELECT * FROM monthly_aggregates WHERE user_id = ? AND month = ?",
                (user_id, month),
            ).fetchone()
        finally:
            conn.close()

        return UsageSummary(
            user_id=user_id,
            today_tokens=d_row["total_tokens"] if d_row else 0,
            month_tokens=m_row["total_tokens"] if m_row else 0,
            today_requests=d_row["request_count"] if d_row else 0,
            month_requests=m_row["request_count"] if m_row else 0,
            quota=self.get_quota(user_id),
        )

    def get_usage_records(
        self, user_id: str, date_from: str = "", date_to: str = "", limit: int = 50
    ) -> list[dict]:
        """Get detailed usage records for a user."""
        query = "SELECT * FROM usage_records WHERE user_id = ?"
        params: list[Any] = [user_id]
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        conn = get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_global_summary(self) -> dict:
        """Get global usage statistics across all users."""
        today = _today()
        month = _this_month()
        conn = get_connection()
        try:
            total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            active_users = conn.execute(
                "SELECT COUNT(*) as c FROM users WHERE status = 'active'"
            ).fetchone()["c"]

            today_row = conn.execute(
                "SELECT COALESCE(SUM(total_tokens), 0) as tokens, "
                "COALESCE(SUM(request_count), 0) as requests "
                "FROM daily_aggregates WHERE date = ?",
                (today,),
            ).fetchone()

            month_row = conn.execute(
                "SELECT COALESCE(SUM(total_tokens), 0) as tokens, "
                "COALESCE(SUM(request_count), 0) as requests "
                "FROM monthly_aggregates WHERE month = ?",
                (month,),
            ).fetchone()

            return {
                "total_users": total_users,
                "active_users": active_users,
                "today_tokens": today_row["tokens"],
                "today_requests": today_row["requests"],
                "month_tokens": month_row["tokens"],
                "month_requests": month_row["requests"],
            }
        finally:
            conn.close()

    def get_daily_aggregates(self, date_from: str = "", date_to: str = "") -> list[dict]:
        """Get daily aggregate statistics across all users."""
        query = "SELECT * FROM daily_aggregates"
        params: list[Any] = []
        conditions = []
        if date_from:
            conditions.append("date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("date <= ?")
            params.append(date_to)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY date DESC, total_tokens DESC"

        conn = get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_users_with_usage(self) -> list[dict]:
        """Get all users with their today/month usage joined."""
        today = _today()
        month = _this_month()
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT u.user_id, u.name, u.channel, u.role, u.status,
                          u.created_at,
                          COALESCE(d.total_tokens, 0) as today_tokens,
                          COALESCE(d.request_count, 0) as today_requests,
                          COALESCE(m.total_tokens, 0) as month_tokens,
                          COALESCE(m.request_count, 0) as month_requests,
                          q.daily_token_limit, q.monthly_token_limit,
                          q.concurrent_session_limit, q.rate_limit_per_minute
                   FROM users u
                   LEFT JOIN daily_aggregates d ON u.user_id = d.user_id AND d.date = ?
                   LEFT JOIN monthly_aggregates m ON u.user_id = m.user_id AND m.month = ?
                   LEFT JOIN quotas q ON u.user_id = q.user_id
                   ORDER BY u.created_at DESC""",
                (today, month),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
