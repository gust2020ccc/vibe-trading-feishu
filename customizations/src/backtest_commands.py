"""Feishu /backtest command handler for direct strategy backtesting.

Commands:
    /backtest                                              Show command help
    /backtest list                                         List available strategies
    /backtest <strategy> <codes> <start> <end> [k=v ...]   Run a backtest

Examples:
    /backtest ma_cross 000001.SZ 2024-01-01 2024-12-31
    /backtest rsi_reversal 600519.SH 2023-01-01 2024-12-31 rsi_period=10 oversold=25
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SEPARATOR = "━━━━━━━━━━━━━━━━━━"


def handle_backtest_command(
    sender_id: str,
    subcommand_text: str,
    *,
    channel: str = "feishu",
    chat_id: str = "",
    bus=None,
) -> str:
    """Execute a /backtest subcommand and return the reply text.

    Args:
        sender_id: The sender's channel ID (e.g. Feishu open_id).
        subcommand_text: The text after /backtest (e.g. "list", or
            "ma_cross 000001.SZ 2024-01-01 2024-12-31 fast=5 slow=20").
        channel: Channel name (e.g. "feishu").
        chat_id: Chat identifier for chart media delivery.
        bus: Optional message bus; when provided and a chart is generated,
            an ``OutboundMessage`` with ``media=[chart_path]`` is published
            so the channel can send the equity/drawdown image.

    Returns:
        Plain text reply suitable for a Feishu message.
    """
    parts = subcommand_text.split()

    # No subcommand -> help
    if not parts or not parts[0]:
        return _format_help()

    sub = parts[0].lower()

    if sub in ("help", "?", "h"):
        return _format_help()

    if sub == "list":
        return _format_strategy_list()

    # Otherwise treat the whole line as a backtest run request
    return _run_backtest(
        parts,
        sender_id=sender_id,
        channel=channel,
        chat_id=chat_id,
        bus=bus,
    )


# --------------------------------------------------------------------------- #
# Backtest execution
# --------------------------------------------------------------------------- #
def _run_backtest(
    parts: list[str],
    *,
    sender_id: str,
    channel: str,
    chat_id: str,
    bus,
) -> str:
    """Parse and execute a backtest run request."""
    if len(parts) < 4:
        return (
            "❌ 参数不足。\n\n"
            "用法: /backtest <策略> <代码> <开始日期> <结束日期> [参数=值 ...]\n\n"
            + _format_help()
        )

    strategy_id = parts[0]
    codes_raw = parts[1]
    start_date = parts[2]
    end_date = parts[3]
    kv_parts = parts[4:]

    # --- Resolve strategy template ----------------------------------------- #
    try:
        from src.backtest.templates import get_strategy
    except Exception:  # noqa: BLE001
        logger.exception("Failed to import backtest templates module")
        return "❌ 回测模块未启用（src.backtest.templates 不可用）。"

    try:
        strategy = get_strategy(strategy_id)
    except Exception:  # noqa: BLE001
        logger.exception("get_strategy raised for %s", strategy_id)
        strategy = None

    if not strategy:
        return (
            f"❌ 未找到策略 '{strategy_id}'。\n\n"
            + _format_strategy_list()
        )

    strategy_name = _attr(strategy, "name", "") or _attr(strategy, "title", "") or strategy_id

    # --- Normalize A-share codes ------------------------------------------- #
    codes_list = _normalize_codes(codes_raw)
    if not codes_list:
        return (
            f"❌ 未提供有效的标的代码: '{codes_raw}'\n"
            "示例: 000001.SZ 或 000001,600519.SH"
        )

    # --- Parse key=value params -------------------------------------------- #
    params = _parse_kv_params(kv_parts)

    # --- Execute the direct backtest --------------------------------------- #
    try:
        from src.backtest.direct_runner import run_direct_backtest
    except Exception:  # noqa: BLE001
        logger.exception("Failed to import src.backtest.direct_runner")
        return "❌ 回测执行器未启用（src.backtest.direct_runner 不可用）。"

    logger.info(
        "Backtest run: strategy=%s codes=%s %s~%s params=%s (sender=%s)",
        strategy_id, codes_list, start_date, end_date, params, sender_id,
    )

    try:
        result = run_direct_backtest(
            strategy_id=strategy_id,
            codes=codes_list,
            start_date=start_date,
            end_date=end_date,
            params=params,
            source="akshare",
            initial_cash=1000000.0,
            interval="1D",
            generate_chart=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_direct_backtest raised for %s", strategy_id)
        return _format_error(
            strategy_name=strategy_name,
            codes=codes_list,
            start_date=start_date,
            end_date=end_date,
            detail=f"{type(exc).__name__}: {exc}",
        )

    # --- Inspect the result ------------------------------------------------ #
    if not isinstance(result, dict):
        return _format_error(
            strategy_name=strategy_name,
            codes=codes_list,
            start_date=start_date,
            end_date=end_date,
            detail=f"意外的返回类型: {type(result).__name__}",
        )

    returncode = _coerce_int(result.get("returncode"), default=0)
    status = str(result.get("status", "") or "").lower()
    failed = returncode != 0 or status in ("error", "failed", "failure")

    run_dir = result.get("run_dir") or result.get("run_directory") or ""
    run_id = result.get("run_id") or result.get("run_name") or (
        Path(str(run_dir)).name if run_dir else ""
    )
    chart_path = result.get("chart_path") or result.get("chart")

    if failed:
        stderr = result.get("stderr") or result.get("error") or result.get("stdout") or ""
        return _format_error(
            strategy_name=strategy_name,
            codes=codes_list,
            start_date=start_date,
            end_date=end_date,
            detail=stderr,
            run_id=run_id,
        )

    # --- Read metrics + format the success reply --------------------------- #
    metrics = {}
    if run_dir:
        try:
            from src.backtest.charts import generate_metrics_summary
            metrics = generate_metrics_summary(Path(run_dir)) or {}
        except Exception:  # noqa: BLE001
            logger.exception("generate_metrics_summary failed for %s", run_dir)
            metrics = {}

    reply = _format_result(
        strategy_name=strategy_name,
        codes=codes_list,
        start_date=start_date,
        end_date=end_date,
        params=params,
        metrics=metrics,
        run_id=run_id,
    )

    # --- Best-effort chart delivery over the bus --------------------------- #
    if bus is not None and chart_path:
        _publish_outbound_chart(
            bus,
            channel=channel,
            chat_id=chat_id,
            chart_path=chart_path,
            run_id=run_id,
            caption=f"📈 回测图表 - {strategy_name}",
        )

    return reply


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
def _normalize_codes(codes_raw: str) -> list[str]:
    """Split comma-separated codes and normalize A-share suffixes."""
    try:
        from src.backtest.templates import normalize_a_share_code
    except Exception:  # noqa: BLE001
        logger.debug("normalize_a_share_code unavailable; using raw codes")
        normalize_a_share_code = None

    out: list[str] = []
    for token in str(codes_raw).split(","):
        token = token.strip()
        if not token:
            continue
        if normalize_a_share_code is not None:
            try:
                normalized = normalize_a_share_code(token)
            except Exception:  # noqa: BLE001
                normalized = token
        else:
            normalized = token
        if normalized:
            out.append(str(normalized))
    return out


def _parse_kv_params(kv_parts: list[str]) -> dict:
    """Parse trailing ``key=value`` arguments.

    Each value is coerced to int first, then float, then kept as a string.
    Tokens without ``=`` are ignored.
    """
    params: dict = {}
    for token in kv_parts:
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        key = key.strip()
        if not key:
            continue
        params[key] = _coerce_value(value.strip())
    return params


def _coerce_value(raw: str):
    """Try int, then float, then string."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _coerce_int(val, *, default: int = 0) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _attr(obj, key, default=None):
    """Read ``key`` from a dict or an object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def _fmt_pct(val, *, signed: bool = False) -> str:
    """Format a metric as a percentage string.

    Values whose absolute magnitude is <= 1 are treated as decimal fractions
    (e.g. 0.1532 -> 15.32%). When ``signed`` is True, positive values are
    prefixed with ``+``.
    """
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return "N/A"
    if abs(fval) <= 1:
        fval = fval * 100
    sign = "+" if signed and fval > 0 else ""
    return f"{sign}{fval:.2f}%"


def _fmt_num(val, ndigits: int = 2) -> str:
    try:
        return f"{float(val):.{ndigits}f}"
    except (ValueError, TypeError):
        return "N/A"


def _fmt_int(val) -> str:
    try:
        return str(int(float(val)))
    except (ValueError, TypeError):
        return "N/A"


def _format_params_line(params: dict) -> str:
    if not params:
        return "默认"
    return ", ".join(f"{k}={v}" for k, v in params.items())


def _format_result(
    *,
    strategy_name: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    params: dict,
    metrics: dict,
    run_id: str,
) -> str:
    """Format the success reply (plain text for Feishu)."""
    total_return = metrics.get("total_return")
    annual_return = metrics.get("annual_return")
    sharpe = metrics.get("sharpe")
    max_drawdown = metrics.get("max_drawdown")
    win_rate = metrics.get("win_rate")
    trade_count = metrics.get("trade_count")

    lines = [
        f"📊 回测结果: {strategy_name}",
        _SEPARATOR,
        f"标的: {', '.join(codes)}",
        f"区间: {start_date} ~ {end_date}",
        f"参数: {_format_params_line(params)}",
        _SEPARATOR,
        f"总收益: {_fmt_pct(total_return, signed=True)}",
        f"年化收益: {_fmt_pct(annual_return, signed=True)}",
        f"夏普比率: {_fmt_num(sharpe)}",
        f"最大回撤: {_fmt_pct(max_drawdown)}",
        f"胜率: {_fmt_pct(win_rate)}",
        f"交易次数: {_fmt_int(trade_count)}",
        _SEPARATOR,
        f"Run ID: {run_id}" if run_id else "Run ID: N/A",
    ]
    return "\n".join(lines)


def _format_error(
    *,
    strategy_name: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    detail: str,
    run_id: str = "",
) -> str:
    """Format a failure reply, including the tail of stderr/error output."""
    tail = ""
    if detail:
        # Keep the last ~800 chars to avoid blowing up the Feishu message.
        tail = detail.strip()[-800:]

    lines = [
        "❌ 回测执行失败",
        "",
        f"策略: {strategy_name}",
        f"标的: {', '.join(codes)}",
        f"区间: {start_date} ~ {end_date}",
    ]
    if run_id:
        lines.append(f"Run ID: {run_id}")
    if tail:
        lines.append("")
        lines.append("错误信息(末尾):")
        lines.append(tail)
    lines.append("")
    lines.append("提示: 检查策略名称、标的代码与日期区间后重试。")
    return "\n".join(lines)


def _format_strategy_list() -> str:
    """List the available strategy templates, grouped by source/tier."""
    strategies: list = []
    try:
        from src.backtest.templates import list_strategies
        strategies = list_strategies() or []
    except Exception:  # noqa: BLE001
        logger.exception("Failed to list backtest strategies")

    if not strategies:
        return "❌ 无法加载策略列表（src.backtest.templates 不可用）。"

    # Split into system (standard) and custom (advanced)
    system_strats = [s for s in strategies if _attr(s, "source", "system") == "system"]
    custom_strats = [s for s in strategies if _attr(s, "source", "system") == "custom"]

    lines = ["📋 可用回测策略", _SEPARATOR]

    if system_strats:
        lines.append("")
        lines.append("🔹 系统策略 (标准)")
        for idx, strategy in enumerate(system_strats, 1):
            sid = _attr(strategy, "id", "")
            name = _attr(strategy, "name", "") or sid
            desc = _attr(strategy, "description", "")
            lines.append(f"  {idx}. {sid} — {name}")
            if desc:
                lines.append(f"     {_truncate(desc, 56)}")

    if custom_strats:
        lines.append("")
        lines.append("⭐ 定制策略 (高级)")
        for idx, strategy in enumerate(custom_strats, 1):
            sid = _attr(strategy, "id", "")
            name = _attr(strategy, "name", "") or sid
            desc = _attr(strategy, "description", "")
            lines.append(f"  {idx}. {sid} — {name}")
            if desc:
                lines.append(f"     {_truncate(desc, 56)}")

    lines.append("")
    lines.append(_SEPARATOR)
    lines.append("用法: /backtest <策略> <代码> <开始> <结束> [参数=值 ...]")
    lines.append("示例: /backtest brick_reversal 000001.SZ 2024-01-01 2026-07-30")
    return "\n".join(lines)


def _format_help() -> str:
    """Format the /backtest help text."""
    return (
        "📖 /backtest 命令帮助\n"
        "\n"
        "用法:\n"
        "  /backtest                                       显示此帮助\n"
        "  /backtest list                                  列出可用策略\n"
        "  /backtest <策略> <代码> <开始> <结束> [参数=值 ...]  运行回测\n"
        "\n"
        "示例:\n"
        "  /backtest ma_cross 000001.SZ 2024-01-01 2024-12-31\n"
        "  /backtest rsi_reversal 600519.SH 2023-01-01 2024-12-31 rsi_period=10 oversold=25\n"
        "\n"
        "说明:\n"
        "  • 代码支持逗号分隔多个标的，自动补全 A 股后缀 (.SH/.SZ)\n"
        "  • 日期格式: YYYY-MM-DD\n"
        "  • 参数以 key=value 形式追加，自动识别 整数/浮点/字符串\n"
        "  • 回测完成后若生成图表，将自动发送净值/回撤图"
    )


def _truncate(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --------------------------------------------------------------------------- #
# Bus chart delivery
# --------------------------------------------------------------------------- #
def _publish_outbound_chart(
    bus,
    *,
    channel: str,
    chat_id: str,
    chart_path,
    run_id: str,
    caption: str,
) -> None:
    """Best-effort publish of a chart image OutboundMessage on the bus.

    The command handler is synchronous, but it is normally invoked from the
    async ``ChannelRuntime``. We therefore schedule the coroutine on the
    running loop when one exists, and otherwise run it to completion.
    """
    import asyncio

    try:
        from src.channels.bus.events import OutboundMessage
    except Exception:  # noqa: BLE001
        logger.warning("OutboundMessage unavailable; cannot publish chart")
        return

    msg = OutboundMessage(
        channel=channel,
        chat_id=chat_id,
        content=caption,
        media=[str(chart_path)],
        metadata={
            "_channel_runtime": True,
            "_backtest_chart": True,
            "run_id": run_id,
        },
    )

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        logger.debug("No event loop available to publish backtest chart")
        return

    coro = bus.publish_outbound(msg)
    try:
        if loop.is_running():
            asyncio.ensure_future(coro, loop=loop)
        else:
            loop.run_until_complete(coro)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to publish backtest chart on the bus", exc_info=True)
