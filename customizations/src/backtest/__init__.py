"""Backtest customization package: templates, direct runner, charts, dashboard."""

from src.backtest.templates import (
    STRATEGY_TEMPLATES,
    generate_signal_engine,
    get_strategy,
    list_strategies,
    normalize_a_share_code,
)

__all__ = [
    "STRATEGY_TEMPLATES",
    "generate_signal_engine",
    "get_strategy",
    "list_strategies",
    "normalize_a_share_code",
]
