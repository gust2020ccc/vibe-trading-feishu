"""Data classes for strategies, factors, and related entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Strategy:
    """A user-defined backtest strategy (signal_engine.py)."""

    id: str
    user_id: str
    name: str
    name_en: str = ""
    description: str = ""
    category: str = "custom"          # trend/reversal/momentum/...
    tags: list[str] = field(default_factory=list)
    source_code: str = ""
    meta: dict[str, Any] = field(default_factory=dict)  # {parameters, markets}
    version: int = 1
    status: str = "draft"             # draft/testing/published/archived
    parent_id: str | None = None      # clone source
    is_public: bool = False
    market_desc: str = ""
    subscriber_count: int = 0
    clone_count: int = 0
    rating_avg: float = 0.0
    rating_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self, include_code: bool = False) -> dict[str, Any]:
        """Return a serialisable dict. Source code is excluded by default."""
        d = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "name_en": self.name_en,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "meta": self.meta,
            "version": self.version,
            "status": self.status,
            "parent_id": self.parent_id,
            "is_public": self.is_public,
            "market_desc": self.market_desc,
            "subscriber_count": self.subscriber_count,
            "clone_count": self.clone_count,
            "rating_avg": self.rating_avg,
            "rating_count": self.rating_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_code:
            d["source_code"] = self.source_code
        return d


@dataclass
class StrategyVersion:
    """A historical snapshot of a strategy."""

    id: str
    strategy_id: str
    version: int
    source_code: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    changelog: str = ""
    created_at: str = ""

    def to_dict(self, include_code: bool = False) -> dict[str, Any]:
        d = {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "version": self.version,
            "meta": self.meta,
            "changelog": self.changelog,
            "created_at": self.created_at,
        }
        if include_code:
            d["source_code"] = self.source_code
        return d


@dataclass
class Factor:
    """A user-defined alpha factor (compute(panel))."""

    id: str
    user_id: str
    name: str
    name_en: str = ""
    description: str = ""
    category: str = "custom"
    tags: list[str] = field(default_factory=list)
    source_code: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    status: str = "draft"
    parent_id: str | None = None
    is_public: bool = False
    market_desc: str = ""
    subscriber_count: int = 0
    clone_count: int = 0
    rating_avg: float = 0.0
    rating_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self, include_code: bool = False) -> dict[str, Any]:
        d = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "name_en": self.name_en,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "meta": self.meta,
            "version": self.version,
            "status": self.status,
            "parent_id": self.parent_id,
            "is_public": self.is_public,
            "market_desc": self.market_desc,
            "subscriber_count": self.subscriber_count,
            "clone_count": self.clone_count,
            "rating_avg": self.rating_avg,
            "rating_count": self.rating_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_code:
            d["source_code"] = self.source_code
        return d


@dataclass
class FactorVersion:
    """A historical snapshot of a factor."""

    id: str
    factor_id: str
    version: int
    source_code: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    changelog: str = ""
    created_at: str = ""

    def to_dict(self, include_code: bool = False) -> dict[str, Any]:
        d = {
            "id": self.id,
            "factor_id": self.factor_id,
            "version": self.version,
            "meta": self.meta,
            "changelog": self.changelog,
            "created_at": self.created_at,
        }
        if include_code:
            d["source_code"] = self.source_code
        return d


@dataclass
class FactorPortfolio:
    """A multi-factor combination configuration."""

    id: str
    user_id: str
    name: str
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    status: str = "draft"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
