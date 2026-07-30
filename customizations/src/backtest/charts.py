"""Generate matplotlib chart PNGs for backtest results.

Reads run artifacts (equity.csv, trades.csv, metrics.csv) and the run config,
then renders a professional two-panel chart: an equity curve (with optional
benchmark overlay and buy/sell markers) on top, and a drawdown area plot below.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Color scheme
# --------------------------------------------------------------------------- #
COLOR_EQUITY = "#2196F3"
COLOR_BENCHMARK = "#FF9800"
COLOR_DRAWDOWN = "#F44336"
COLOR_BUY = "#4CAF50"
COLOR_SELL = "#F44336"
COLOR_GRID = "lightgray"
GRID_ALPHA = 0.3

# --------------------------------------------------------------------------- #
# Chinese font setup (fall back to English labels if unavailable)
# --------------------------------------------------------------------------- #
_CN_FONT_CANDIDATES = [
    "SimHei",
    "Microsoft YaHei",
    "STHeiti",
    "PingFang SC",
    "Heiti SC",
    "Arial Unicode MS",
    "WenQuanYi Micro Hei",
    "Noto Sans CJK SC",
]


def _detect_chinese_font() -> bool:
    """Try to activate a Chinese-capable font. Return True if one is available."""
    available = {f.name for f in fm.fontManager.ttflist}
    for name in _CN_FONT_CANDIDATES:
        if name in available:
            matplotlib.rcParams["font.sans-serif"] = [
                name,
                *matplotlib.rcParams.get("font.sans-serif", []),
            ]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return True
    logger.warning("No Chinese font found; falling back to English labels.")
    return False


_HAS_CN = _detect_chinese_font()

# --------------------------------------------------------------------------- #
# Localized labels
# --------------------------------------------------------------------------- #
if _HAS_CN:
    _L = {
        "equity_label": "净值曲线",
        "benchmark_label": "基准",
        "drawdown_label": "回撤",
        "buy_label": "买入",
        "sell_label": "卖出",
        "total_return": "总收益",
        "annual_return": "年化收益",
        "sharpe": "夏普比率",
        "max_drawdown": "最大回撤",
        "win_rate": "胜率",
        "trades_label": "交易",
        "no_data": "无数据",
    }
else:
    _L = {
        "equity_label": "Equity",
        "benchmark_label": "Benchmark",
        "drawdown_label": "Drawdown",
        "buy_label": "Buy",
        "sell_label": "Sell",
        "total_return": "Total Return",
        "annual_return": "Annual Return",
        "sharpe": "Sharpe",
        "max_drawdown": "Max Drawdown",
        "win_rate": "Win Rate",
        "trades_label": "Trades",
        "no_data": "No data",
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _read_metrics(metrics_path: Path) -> dict:
    """Read metrics.csv into a dict, supporting long and wide formats."""
    if not metrics_path.exists():
        return {}
    try:
        mdf = pd.read_csv(metrics_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read metrics.csv (%s): %s", metrics_path, exc)
        return {}
    if mdf.empty:
        return {}
    # Long format: columns [metric, value]
    if "metric" in mdf.columns and "value" in mdf.columns:
        return dict(zip(mdf["metric"], mdf["value"]))
    # Wide format: single row of named columns
    row = mdf.iloc[0].to_dict()
    return {k: v for k, v in row.items() if pd.notna(v)}


def _pct(val) -> str:
    """Format a value as a percentage string (handles decimal or percent form)."""
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return "N/A"
    if abs(fval) <= 1:
        fval = fval * 100
    return f"{fval:.2f}%"


def _num(val) -> str:
    """Format a plain numeric value."""
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return "N/A"
    return f"{fval:.4f}"


# --------------------------------------------------------------------------- #
# Public API: metrics summary
# --------------------------------------------------------------------------- #
def generate_metrics_summary(run_dir: Path) -> dict:
    """Read metrics.csv and return a dict of key metrics.

    Returns a dict with keys: total_return, annual_return, max_drawdown,
    sharpe, win_rate, trade_count, final_value. Missing values are None.
    """
    run_dir = Path(run_dir)
    metrics_path = run_dir / "artifacts" / "metrics.csv"
    raw = _read_metrics(metrics_path)

    def _first(*keys):
        for k in keys:
            if k in raw and pd.notna(raw[k]):
                return raw[k]
        return None

    return {
        "total_return": _first("total_return", "totalReturn", "return"),
        "annual_return": _first(
            "annual_return", "annualReturn", "annualized_return", "cagr"
        ),
        "max_drawdown": _first("max_drawdown", "maxDrawdown", "max_dd"),
        "sharpe": _first("sharpe", "sharpe_ratio", "sharpeRatio"),
        "win_rate": _first("win_rate", "winRate", "hit_rate"),
        "trade_count": _first(
            "trade_count", "tradeCount", "num_trades", "total_trades", "trades"
        ),
        "final_value": _first(
            "final_value", "finalValue", "final_equity", "end_value"
        ),
    }


# --------------------------------------------------------------------------- #
# Public API: backtest chart
# --------------------------------------------------------------------------- #
def generate_backtest_chart(
    run_dir: Path, output_path: Path | None = None
) -> Path | None:
    """Generate a backtest equity/drawdown chart PNG.

    Reads ``{run_dir}/artifacts/equity.csv`` (columns: ret, equity, drawdown,
    benchmark_equity, active_ret) and ``{run_dir}/artifacts/trades.csv``
    (columns: timestamp, code, side, price, qty, reason, pnl, holding_days,
    return_pct). Strategy info is pulled from ``{run_dir}/config.json`` and key
    metrics from ``{run_dir}/artifacts/metrics.csv``.

    Args:
        run_dir: Backtest run directory containing ``artifacts/`` and ``config.json``.
        output_path: Destination PNG path. When ``None`` the chart is saved to
            ``{run_dir}/artifacts/chart.png``.

    Returns:
        Path to the generated PNG, or ``None`` if the equity data is missing
        or empty.
    """
    run_dir = Path(run_dir)
    artifacts_dir = run_dir / "artifacts"
    equity_path = artifacts_dir / "equity.csv"
    trades_path = artifacts_dir / "trades.csv"
    config_path = run_dir / "config.json"
    metrics_path = artifacts_dir / "metrics.csv"

    # --- equity ------------------------------------------------------------- #
    if not equity_path.exists():
        logger.warning("equity.csv not found: %s", equity_path)
        return None

    try:
        equity_df = pd.read_csv(equity_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read equity.csv (%s): %s", equity_path, exc)
        return None

    if equity_df.empty:
        logger.warning("equity.csv is empty: %s", equity_path)
        return None

    # Identify / parse the date index. The first column is commonly the date
    # when the CSV was written with ``index=True``.
    date_col: str | None = None
    for cand in ("date", "datetime", "timestamp", "time", "Unnamed: 0"):
        if cand in equity_df.columns:
            date_col = cand
            break

    if date_col is not None:
        equity_df[date_col] = pd.to_datetime(
            equity_df[date_col], errors="coerce"
        )
        equity_df = equity_df.dropna(subset=[date_col])
        if equity_df.empty:
            logger.warning("equity.csv has no valid dates after parsing.")
            return None
        equity_df = equity_df.set_index(date_col)
        equity_df = equity_df.sort_index()

    has_datetime_index = isinstance(equity_df.index, pd.DatetimeIndex)

    # --- config ------------------------------------------------------------- #
    strategy_name = ""
    codes = ""
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as fh:
                config = json.load(fh)
            strategy_name = str(
                config.get("strategy", config.get("strategy_name", ""))
            )
            codes_val = config.get("codes", config.get("symbols", config.get("universe", "")))
            if isinstance(codes_val, (list, tuple)):
                codes = ", ".join(str(c) for c in codes_val)
            else:
                codes = str(codes_val) if codes_val else ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read config.json (%s): %s", config_path, exc)

    # --- trades ------------------------------------------------------------- #
    trades_df: pd.DataFrame | None = None
    if trades_path.exists():
        try:
            trades_df = pd.read_csv(trades_path)
            if not trades_df.empty and "timestamp" in trades_df.columns:
                trades_df["timestamp"] = pd.to_datetime(
                    trades_df["timestamp"], errors="coerce"
                )
                trades_df = trades_df.dropna(subset=["timestamp"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read trades.csv (%s): %s", trades_path, exc)
            trades_df = None
    else:
        logger.info("trades.csv not found; skipping buy/sell markers.")

    # --- metrics ------------------------------------------------------------ #
    metrics = _read_metrics(metrics_path)

    def _metric(*keys) -> object | None:
        for k in keys:
            if k in metrics and pd.notna(metrics[k]):
                return metrics[k]
        return None

    # --- build figure ------------------------------------------------------- #
    fig, (ax_equity, ax_dd) = plt.subplots(
        2,
        1,
        figsize=(12, 6),
        dpi=100,
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )
    fig.patch.set_facecolor("white")

    # Equity curve
    if "equity" in equity_df.columns:
        ax_equity.plot(
            equity_df.index,
            equity_df["equity"],
            color=COLOR_EQUITY,
            linewidth=1.5,
            label=_L["equity_label"],
            zorder=3,
        )

    # Benchmark overlay (optional)
    benchmark_present = (
        "benchmark_equity" in equity_df.columns
        and equity_df["benchmark_equity"].notna().any()
    )
    if benchmark_present:
        ax_equity.plot(
            equity_df.index,
            equity_df["benchmark_equity"],
            color=COLOR_BENCHMARK,
            linewidth=1.2,
            label=_L["benchmark_label"],
            alpha=0.85,
            zorder=2,
        )

    ax_equity.set_facecolor("white")
    ax_equity.grid(True, color=COLOR_GRID, alpha=GRID_ALPHA)

    # Buy / sell markers
    if (
        trades_df is not None
        and not trades_df.empty
        and "equity" in equity_df.columns
        and "side" in trades_df.columns
        and has_datetime_index
    ):
        eq_series = equity_df["equity"]

        def _nearest_point(ts: pd.Timestamp):
            """Return (x, y) of the equity point nearest to *ts*."""
            try:
                i = eq_series.index.get_indexer([ts], method="nearest")[0]
            except (KeyError, ValueError, TypeError):
                return None, None
            if i < 0 or i >= len(eq_series):
                return None, None
            return eq_series.index[i], eq_series.iloc[i]

        for side, color, marker, label in [
            ("buy", COLOR_BUY, "^", _L["buy_label"]),
            ("sell", COLOR_SELL, "v", _L["sell_label"]),
        ]:
            subset = trades_df[
                trades_df["side"].astype(str).str.lower() == side
            ]
            if subset.empty:
                continue
            xs, ys = [], []
            for ts in subset["timestamp"]:
                x, y = _nearest_point(ts)
                if x is not None:
                    xs.append(x)
                    ys.append(y)
            if xs:
                ax_equity.scatter(
                    xs,
                    ys,
                    color=color,
                    marker=marker,
                    s=55,
                    zorder=5,
                    label=label,
                    edgecolors="white",
                    linewidths=0.5,
                )

    # Combine legend entries (avoid duplicate labels)
    handles, labels = ax_equity.get_legend_handles_labels()
    seen: set[str] = set()
    unique_handles, unique_labels = [], []
    for h, lbl in zip(handles, labels):
        if lbl not in seen:
            seen.add(lbl)
            unique_handles.append(h)
            unique_labels.append(lbl)
    if unique_handles:
        ax_equity.legend(
            unique_handles,
            unique_labels,
            loc="best",
            fontsize=9,
            framealpha=0.85,
        )

    # Key-metrics text box
    metrics_lines = [
        f"{_L['total_return']}: {_pct(_metric('total_return', 'totalReturn', 'return'))}",
        f"{_L['annual_return']}: {_pct(_metric('annual_return', 'annualReturn', 'annualized_return', 'cagr'))}",
        f"{_L['sharpe']}: {_num(_metric('sharpe', 'sharpe_ratio', 'sharpeRatio'))}",
        f"{_L['max_drawdown']}: {_pct(_metric('max_drawdown', 'maxDrawdown', 'max_dd'))}",
        f"{_L['win_rate']}: {_pct(_metric('win_rate', 'winRate', 'hit_rate'))}",
    ]
    metrics_text = "\n".join(metrics_lines)
    ax_equity.text(
        0.012,
        0.985,
        metrics_text,
        transform=ax_equity.transAxes,
        fontsize=9,
        verticalalignment="top",
        family="monospace",
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor="white",
            edgecolor="#BDBDBD",
            alpha=0.85,
        ),
        zorder=6,
    )

    # Drawdown panel
    if "drawdown" in equity_df.columns:
        dd = equity_df["drawdown"]
        ax_dd.fill_between(
            equity_df.index,
            dd,
            0,
            color=COLOR_DRAWDOWN,
            alpha=0.3,
            zorder=1,
        )
        ax_dd.plot(
            equity_df.index,
            dd,
            color=COLOR_DRAWDOWN,
            linewidth=1,
            zorder=2,
        )

    ax_dd.set_facecolor("white")
    ax_dd.grid(True, color=COLOR_GRID, alpha=GRID_ALPHA)
    ax_dd.set_ylabel(_L["drawdown_label"], fontsize=9)

    # X-axis date formatting
    if has_datetime_index:
        try:
            import matplotlib.dates as mdates

            ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
            fig.autofmt_xdate(rotation=30)
        except Exception:  # noqa: BLE001
            pass

    # Title with strategy name, codes and date range
    if has_datetime_index and len(equity_df.index) > 0:
        start = pd.Timestamp(equity_df.index[0]).strftime("%Y-%m-%d")
        end = pd.Timestamp(equity_df.index[-1]).strftime("%Y-%m-%d")
        date_range = f"{start} ~ {end}"
    else:
        date_range = ""

    title_parts: list[str] = []
    if strategy_name:
        title_parts.append(strategy_name)
    if codes:
        title_parts.append(codes)
    title_head = " | ".join(title_parts) if title_parts else _L["no_data"]
    title = f"{title_head}\n{date_range}" if date_range else title_head
    fig.suptitle(title, fontsize=12, fontweight="bold")

    # Layout & save
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    if output_path is None:
        output_path = artifacts_dir / "chart.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        fig.savefig(output_path, dpi=100, facecolor="white")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save chart to %s: %s", output_path, exc)
        plt.close(fig)
        return None
    finally:
        plt.close(fig)

    logger.info("Backtest chart saved to %s", output_path)
    return output_path
