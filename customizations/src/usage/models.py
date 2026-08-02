"""Data classes for the usage tracking system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    """A registered user identified by their channel sender_id (Feishu open_id)."""

    user_id: str
    name: str = ""
    email: str = ""
    password_hash: str = ""
    channel: str = "feishu"
    role: str = "user"          # user / admin / operator
    status: str = "active"      # active / disabled
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Quota:
    """Per-user quota limits. A value of 0 means unlimited."""

    user_id: str
    daily_token_limit: int = 0         # 0 = unlimited
    monthly_token_limit: int = 0
    concurrent_session_limit: int = 0
    rate_limit_per_minute: int = 0


@dataclass
class QuotaCheckResult:
    """Result of a quota check before processing a user message."""

    allowed: bool
    reason: str = ""           # rate_limited / daily_exceeded / monthly_exceeded / concurrent_exceeded / disabled
    deny_message: str = ""     # Text to send back to the user
    current_usage: dict = field(default_factory=dict)


@dataclass
class UsageSummary:
    """Aggregated usage summary for a user."""

    user_id: str
    today_tokens: int = 0
    month_tokens: int = 0
    today_requests: int = 0
    month_requests: int = 0
    quota: Optional[Quota] = None
