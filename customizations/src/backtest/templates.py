"""Strategy template library for direct backtest execution.

Each template dynamically generates a compliant ``signal_engine.py`` source
string that passes the AST safety validation in ``backtest.runner``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Code templates
#
# IMPORTANT: These strings use ``str.format()`` so literal braces in dict
# literals must be doubled: ``{{}}`` → ``{}``.
# --------------------------------------------------------------------------- #

_MA_CROSS_TEMPLATE = '''"""均线交叉策略 - auto generated"""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    def __init__(self, fast_period: int = {fast_period}, slow_period: int = {slow_period}):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {{}}
        for code, df in data_map.items():
            close = df["close"]
            ma_fast = close.rolling(self.fast_period).mean()
            ma_slow = close.rolling(self.slow_period).mean()
            raw = (ma_fast > ma_slow).astype(int)
            # Only signal on crossover change
            signal = raw.diff().fillna(raw)
            signal = signal.where(signal != 0, 0).astype(int)
            result[code] = signal.fillna(0)
        return result
'''

_RSI_REVERSAL_TEMPLATE = '''"""RSI超买超卖策略 - auto generated"""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    def __init__(self, rsi_period: int = {rsi_period}, oversold: float = {oversold}, overbought: float = {overbought}):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {{}}
        for code, df in data_map.items():
            close = df["close"]
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(self.rsi_period).mean()
            loss = (-delta.clip(upper=0)).rolling(self.rsi_period).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            signal = pd.Series(0, index=close.index, dtype=int)
            signal[rsi < self.oversold] = 1
            signal[rsi > self.overbought] = -1
            result[code] = signal
        return result
'''

_MACD_CROSS_TEMPLATE = '''"""MACD交叉策略 - auto generated"""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    def __init__(self, fast: int = {fast}, slow: int = {slow}, signal_period: int = {signal}):
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {{}}
        for code, df in data_map.items():
            close = df["close"]
            ema_fast = close.ewm(span=self.fast, adjust=False).mean()
            ema_slow = close.ewm(span=self.slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
            histogram = macd_line - signal_line
            signal = (histogram > 0).astype(int) * 2 - 1
            signal = signal.where(histogram != 0, 0).astype(int)
            result[code] = signal.fillna(0)
        return result
'''

_BOLLINGER_BREAKOUT_TEMPLATE = '''"""布林带突破策略 - auto generated"""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    def __init__(self, bb_window: int = {bb_window}, bb_std: float = {bb_std}):
        self.bb_window = bb_window
        self.bb_std = bb_std

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {{}}
        for code, df in data_map.items():
            close = df["close"]
            ma = close.rolling(self.bb_window).mean()
            sd = close.rolling(self.bb_window).std()
            upper = ma + self.bb_std * sd
            lower = ma - self.bb_std * sd
            signal = pd.Series(0, index=close.index, dtype=int)
            signal[close > upper] = 1
            signal[close < lower] = -1
            result[code] = signal
        return result
'''

_DUAL_MOMENTUM_TEMPLATE = '''"""双动量策略 - auto generated"""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    def __init__(self, lookback: int = {lookback}, threshold: float = {threshold}):
        self.lookback = lookback
        self.threshold = threshold

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {{}}
        for code, df in data_map.items():
            close = df["close"]
            momentum = close.pct_change(self.lookback)
            signal = pd.Series(0, index=close.index, dtype=int)
            signal[momentum > self.threshold] = 1
            signal[momentum < -self.threshold] = -1
            result[code] = signal
        return result
'''

_MULTI_FACTOR_VOTE_TEMPLATE = '''"""多因子投票策略 - auto generated"""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    def __init__(
        self,
        ema_fast: int = {ema_fast},
        ema_slow: int = {ema_slow},
        rsi_period: int = {rsi_period},
        bb_window: int = {bb_window},
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.bb_window = bb_window

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {{}}
        for code, df in data_map.items():
            close = df["close"]

            # Factor 1: EMA trend
            ef = close.ewm(span=self.ema_fast, adjust=False).mean()
            es = close.ewm(span=self.ema_slow, adjust=False).mean()
            f_trend = pd.Series(0, index=close.index, dtype=int)
            f_trend[ef > es] = 1
            f_trend[ef < es] = -1

            # Factor 2: RSI mean reversion
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(self.rsi_period).mean()
            loss = (-delta.clip(upper=0)).rolling(self.rsi_period).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            f_rsi = pd.Series(0, index=close.index, dtype=int)
            f_rsi[rsi < 30] = 1
            f_rsi[rsi > 70] = -1

            # Factor 3: Bollinger position
            ma = close.rolling(self.bb_window).mean()
            sd = close.rolling(self.bb_window).std()
            lower = ma - 2 * sd
            upper = ma + 2 * sd
            f_bb = pd.Series(0, index=close.index, dtype=int)
            f_bb[close < lower] = 1
            f_bb[close > upper] = -1

            # Majority vote
            votes = f_trend + f_rsi + f_bb
            signal = pd.Series(0, index=close.index, dtype=int)
            signal[votes > 0] = 1
            signal[votes < 0] = -1
            result[code] = signal
        return result
'''


# --------------------------------------------------------------------------- #
# Strategy registry
# --------------------------------------------------------------------------- #

STRATEGY_TEMPLATES: dict[str, dict[str, Any]] = {
    "ma_cross": {
        "name": "均线交叉策略",
        "name_en": "MA Crossover",
        "description": "快慢均线金叉买入、死叉卖出，经典趋势跟踪策略",
        "category": "trend",
        "markets": ["a_share", "hk_equity", "us_equity"],
        "parameters": [
            {"key": "fast_period", "label": "快线周期", "type": "int", "default": 5, "min": 2, "max": 60},
            {"key": "slow_period", "label": "慢线周期", "type": "int", "default": 20, "min": 5, "max": 250},
        ],
        "code_template": _MA_CROSS_TEMPLATE,
    },
    "rsi_reversal": {
        "name": "RSI超买超卖策略",
        "name_en": "RSI Reversal",
        "description": "RSI低于超卖线买入、高于超买线卖出，均值回归策略",
        "category": "mean_reversion",
        "markets": ["a_share", "hk_equity", "us_equity"],
        "parameters": [
            {"key": "rsi_period", "label": "RSI周期", "type": "int", "default": 14, "min": 2, "max": 50},
            {"key": "oversold", "label": "超卖线", "type": "float", "default": 30, "min": 5, "max": 45},
            {"key": "overbought", "label": "超买线", "type": "float", "default": 70, "min": 55, "max": 95},
        ],
        "code_template": _RSI_REVERSAL_TEMPLATE,
    },
    "macd_cross": {
        "name": "MACD交叉策略",
        "name_en": "MACD Crossover",
        "description": "MACD柱状图由负转正买入、由正转负卖出",
        "category": "trend",
        "markets": ["a_share", "hk_equity", "us_equity"],
        "parameters": [
            {"key": "fast", "label": "快线EMA", "type": "int", "default": 12, "min": 2, "max": 50},
            {"key": "slow", "label": "慢线EMA", "type": "int", "default": 26, "min": 5, "max": 100},
            {"key": "signal", "label": "信号线EMA", "type": "int", "default": 9, "min": 2, "max": 30},
        ],
        "code_template": _MACD_CROSS_TEMPLATE,
    },
    "bollinger_breakout": {
        "name": "布林带突破策略",
        "name_en": "Bollinger Breakout",
        "description": "价格突破布林带上轨买入、跌破下轨卖出",
        "category": "breakout",
        "markets": ["a_share", "hk_equity", "us_equity"],
        "parameters": [
            {"key": "bb_window", "label": "布林带窗口", "type": "int", "default": 20, "min": 5, "max": 100},
            {"key": "bb_std", "label": "标准差倍数", "type": "float", "default": 2.0, "min": 0.5, "max": 4.0},
        ],
        "code_template": _BOLLINGER_BREAKOUT_TEMPLATE,
    },
    "dual_momentum": {
        "name": "双动量策略",
        "name_en": "Dual Momentum",
        "description": "基于lookback期收益率的双向动量信号",
        "category": "momentum",
        "markets": ["a_share", "hk_equity", "us_equity"],
        "parameters": [
            {"key": "lookback", "label": "回看周期", "type": "int", "default": 20, "min": 5, "max": 120},
            {"key": "threshold", "label": "动量阈值", "type": "float", "default": 0.0, "min": 0.0, "max": 0.2},
        ],
        "code_template": _DUAL_MOMENTUM_TEMPLATE,
    },
    "multi_factor_vote": {
        "name": "多因子投票策略",
        "name_en": "Multi-Factor Vote",
        "description": "EMA趋势+RSI均值回归+布林带位置三因子投票",
        "category": "composite",
        "markets": ["a_share", "hk_equity", "us_equity"],
        "parameters": [
            {"key": "ema_fast", "label": "EMA快线", "type": "int", "default": 12, "min": 2, "max": 50},
            {"key": "ema_slow", "label": "EMA慢线", "type": "int", "default": 26, "min": 5, "max": 100},
            {"key": "rsi_period", "label": "RSI周期", "type": "int", "default": 14, "min": 2, "max": 50},
            {"key": "bb_window", "label": "布林带窗口", "type": "int", "default": 20, "min": 5, "max": 100},
        ],
        "code_template": _MULTI_FACTOR_VOTE_TEMPLATE,
    },
}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def generate_signal_engine(strategy_id: str, params: dict | None = None) -> str:
    """Generate ``signal_engine.py`` source code from a template.

    Args:
        strategy_id: Key into :data:`STRATEGY_TEMPLATES`.
        params: Optional parameter overrides.  Missing keys fall back to the
            template defaults.

    Returns:
        Ready-to-write Python source string.

    Raises:
        KeyError: If *strategy_id* is not a known template.
    """
    template = STRATEGY_TEMPLATES.get(strategy_id)
    if template is None:
        raise KeyError(f"Unknown strategy template: {strategy_id}")

    # Build the full parameter dict: defaults → overrides
    defaults = {p["key"]: p["default"] for p in template["parameters"]}
    if params:
        for k, v in params.items():
            if k in defaults:
                defaults[k] = v

    code = template["code_template"]
    return code.format(**defaults)


def list_strategies() -> list[dict]:
    """Return a summary list of all strategy templates (without code)."""
    result = []
    for sid, tmpl in STRATEGY_TEMPLATES.items():
        result.append({
            "id": sid,
            "name": tmpl["name"],
            "name_en": tmpl["name_en"],
            "description": tmpl["description"],
            "category": tmpl["category"],
            "markets": tmpl["markets"],
            "parameters": tmpl["parameters"],
        })
    return result


def get_strategy(strategy_id: str) -> dict | None:
    """Return a single strategy template by ID, or ``None`` if not found."""
    tmpl = STRATEGY_TEMPLATES.get(strategy_id)
    if tmpl is None:
        return None
    return {
        "id": strategy_id,
        "name": tmpl["name"],
        "name_en": tmpl["name_en"],
        "description": tmpl["description"],
        "category": tmpl["category"],
        "markets": tmpl["markets"],
        "parameters": tmpl["parameters"],
    }


def normalize_a_share_code(code: str) -> str:
    """Auto-append ``.SZ`` / ``.SH`` suffix for bare 6-digit A-share codes.

    Rules:
        - 6-digit starting with 0 or 3 → ``.SZ`` (Shenzhen stock/创业板)
        - 6-digit starting with 6 → ``.SH`` (Shanghai stock)
        - 6-digit starting with 5 → ``.SH`` (Shanghai ETF/基金)
        - 6-digit starting with 1 → ``.SZ`` (Shenzhen ETF/基金)
        - 6-digit starting with 8 or 4 → ``.BJ`` (Beijing exchange)
        - Already has a suffix (contains ``.``) → unchanged
        - Other formats → unchanged

    Args:
        code: A stock code string, possibly without exchange suffix.

    Returns:
        The normalized code with exchange suffix where applicable.
    """
    code = code.strip()
    if "." in code:
        return code
    if len(code) == 6 and code.isdigit():
        first = code[0]
        if first in ("0", "3"):
            return code + ".SZ"
        if first in ("5", "6", "9"):
            return code + ".SH"
        if first in ("1", "2"):
            return code + ".SZ"
        if first in ("8", "4"):
            return code + ".BJ"
    return code
