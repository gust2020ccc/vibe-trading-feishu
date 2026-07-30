"""Direct backtest executor that bypasses the LLM.

Creates a run directory, writes ``config.json`` and ``code/signal_engine.py``
from a strategy template, then invokes the built-in backtest engine via
``src.tools.backtest_tool.run_backtest()``.

This module is the bridge between the strategy template library
(:mod:`src.backtest.templates`) and the vibe-trading backtest runner
(:mod:`backtest.runner`), enabling instant strategy testing without
natural-language round-trips through the LLM.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-.]+$")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def run_direct_backtest(
    *,
    strategy_id: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    params: dict | None = None,
    source: str = "akshare",
    initial_cash: float = 1_000_000.0,
    interval: str = "1D",
    generate_chart: bool = True,
) -> dict[str, Any]:
    """Execute a direct backtest from a strategy template.

    Creates a unique run directory under ``RUNS_DIR``, writes
    ``config.json`` and ``code/signal_engine.py``, invokes the backtest
    engine, optionally generates a chart, and returns a structured result.

    Args:
        strategy_id: Key into :data:`STRATEGY_TEMPLATES` (e.g. ``"ma_cross"``).
        codes: List of stock codes (e.g. ``["000001.SZ"]``).
        start_date: Backtest start date (``"YYYY-MM-DD"``).
        end_date: Backtest end date (``"YYYY-MM-DD"``).
        params: Optional parameter overrides for the strategy template.
        source: Data source (e.g. ``"auto"``, ``"akshare"``, ``"tushare"``).
        initial_cash: Starting capital for the backtest.
        interval: Bar interval (e.g. ``"1D"``, ``"1H"``).
        generate_chart: If True, generate an equity/drawdown chart PNG.

    Returns:
        A dict with keys:

        - ``status``: ``"ok"`` on success, ``"error"`` on failure.
        - ``returncode``: Process exit code (0 = success).
        - ``run_dir``: Absolute path to the run directory.
        - ``run_id``: The run directory name (timestamp-based).
        - ``chart_path``: Path to the chart PNG (if generated), else ``None``.
        - ``stderr`` / ``stdout``: Captured output (on failure).
        - ``error``: Error message (on failure).
        - ``metrics``: Dict of key metrics (on success).
    """
    from src.backtest.templates import generate_signal_engine, normalize_a_share_code

    # --- Resolve RUNS_DIR -------------------------------------------------- #
    runs_dir = _get_runs_dir()
    runs_dir.mkdir(parents=True, exist_ok=True)

    # --- Create unique run directory --------------------------------------- #
    run_id = _make_run_id(strategy_id)
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "code").mkdir(exist_ok=True)

    # --- Normalize A-share codes (add .SZ/.SH suffix for bare 6-digit codes) #
    normalized_codes = []
    for c in codes:
        try:
            normalized_codes.append(normalize_a_share_code(c))
        except Exception:
            normalized_codes.append(c)
    codes = normalized_codes

    logger.info("Direct backtest: strategy=%s codes=%s run_dir=%s",
                strategy_id, codes, run_dir)

    # --- Write config.json ------------------------------------------------- #
    config: dict[str, Any] = {
        "codes": list(codes),
        "start_date": start_date,
        "end_date": end_date,
        "source": source,
        "interval": interval,
        "initial_cash": float(initial_cash),
    }

    config_path = run_dir / "config.json"
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # --- Generate + write signal_engine.py --------------------------------- #
    try:
        engine_code = generate_signal_engine(strategy_id, params)
    except KeyError as exc:
        return _error_result(run_dir, run_id, f"Unknown strategy: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to generate signal_engine.py")
        return _error_result(run_dir, run_id, f"Code generation error: {exc}")

    signal_path = run_dir / "code" / "signal_engine.py"
    signal_path.write_text(engine_code, encoding="utf-8")

    # --- Execute the backtest engine --------------------------------------- #
    try:
        from src.tools.backtest_tool import run_backtest
    except ImportError:
        # Fallback: try importing from the installed package directly
        try:
            from src.tools.backtest_tool import run_backtest  # noqa: F811
        except ImportError as exc:
            return _error_result(run_dir, run_id,
                                 f"backtest_tool not available: {exc}")

    try:
        raw_result = run_backtest(str(run_dir))
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_backtest raised for %s", run_dir)
        return _error_result(run_dir, run_id, f"Runner error: {exc}")

    # --- Parse the JSON result --------------------------------------------- #
    try:
        result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
    except (json.JSONDecodeError, TypeError) as exc:
        return _error_result(run_dir, run_id,
                             f"Failed to parse runner output: {exc}")

    status = str(result.get("status", "")).lower()
    exit_code = int(result.get("exit_code", -1))
    failed = status == "error" or exit_code != 0

    if failed:
        stderr = result.get("stderr", "") or result.get("stdout", "") or ""
        return _error_result(run_dir, run_id, stderr, exit_code=exit_code)

    # --- Generate chart (optional) ----------------------------------------- #
    chart_path: str | None = None
    if generate_chart:
        try:
            from src.backtest.charts import generate_backtest_chart
            generated = generate_backtest_chart(run_dir)
            if generated is not None:
                chart_path = str(generated)
        except Exception:  # noqa: BLE001
            logger.warning("Chart generation failed for %s", run_dir, exc_info=True)

    # --- Read metrics ------------------------------------------------------ #
    metrics: dict[str, Any] = {}
    try:
        from src.backtest.charts import generate_metrics_summary
        metrics = generate_metrics_summary(run_dir) or {}
    except Exception:  # noqa: BLE001
        logger.debug("metrics summary unavailable", exc_info=True)

    logger.info("Direct backtest completed: %s (status=%s)", run_id, status)

    return {
        "status": "ok",
        "returncode": exit_code,
        "run_dir": str(run_dir),
        "run_id": run_id,
        "chart_path": chart_path,
        "metrics": metrics,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_runs_dir() -> Path:
    """Return the canonical runs directory (imported from ``src.api.helpers``).

    Falls back to ``~/.vibe-trading/runs`` if the API helpers are unavailable.
    Both are accepted run roots by ``safe_run_dir()``.
    """
    try:
        from src.api.helpers import RUNS_DIR
        return Path(RUNS_DIR)
    except ImportError:
        pass
    return Path.home() / ".vibe-trading" / "runs"


def _make_run_id(strategy_id: str) -> str:
    """Generate a unique run directory name.

    Format: ``run_YYYYMMDD_HHMMSS_<strategy_id>_<short_uuid>``
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize strategy_id for filesystem safety
    safe_strategy = re.sub(r"[^A-Za-z0-9_\-]", "_", strategy_id)[:20]
    # Short unique suffix to avoid collisions within the same second
    import uuid
    short_uuid = uuid.uuid4().hex[:6]
    return f"run_{ts}_{safe_strategy}_{short_uuid}"


def _error_result(
    run_dir: Path,
    run_id: str,
    detail: str,
    *,
    exit_code: int = 1,
) -> dict[str, Any]:
    """Build a standardized error result dict."""
    # Truncate long error output
    if detail and len(detail) > 2000:
        detail = detail[-2000:]
    return {
        "status": "error",
        "returncode": exit_code,
        "run_dir": str(run_dir),
        "run_id": run_id,
        "chart_path": None,
        "error": detail,
        "stderr": detail,
        "stdout": "",
        "metrics": {},
    }


# --------------------------------------------------------------------------- #
# Utility: list recent runs
# --------------------------------------------------------------------------- #
def list_recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    """List recent backtest runs from the runs directory.

    Args:
        limit: Maximum number of runs to return.

    Returns:
        List of dicts with ``run_id``, ``status``, ``strategy``, ``codes``,
        ``start_date``, ``end_date``, ``created_at``, and ``has_chart``.
    """
    runs_dir = _get_runs_dir()
    if not runs_dir.exists():
        return []

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("run_")],
        key=lambda x: x.name,
        reverse=True,
    )

    results: list[dict[str, Any]] = []
    for d in run_dirs[:limit]:
        run_id = d.name
        config = _load_json(d / "config.json")
        has_equity = (d / "artifacts" / "equity.csv").exists()
        has_chart = (d / "artifacts" / "chart.png").exists()

        results.append({
            "run_id": run_id,
            "status": "success" if has_equity else "unknown",
            "strategy": _extract_strategy_from_id(run_id),
            "codes": config.get("codes", []),
            "start_date": config.get("start_date", ""),
            "end_date": config.get("end_date", ""),
            "created_at": _parse_run_timestamp(run_id),
            "has_chart": has_chart,
        })

    return results


def _load_json(path: Path) -> dict:
    """Read a JSON file, returning an empty dict on any error."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _extract_strategy_from_id(run_id: str) -> str:
    """Extract the strategy name from a run_id like ``run_20240101_120000_ma_cross_abc123``."""
    parts = run_id.split("_")
    if len(parts) >= 4:
        # run_YYYYMMDD_HHMMSS_<strategy>_<uuid>
        return parts[3]
    return ""


def _parse_run_timestamp(run_id: str) -> str:
    """Parse the timestamp from a run_id into a readable string."""
    parts = run_id.split("_")
    if len(parts) >= 3:
        d_str, t_str = parts[1], parts[2]
        if len(d_str) == 8 and len(t_str) == 6:
            return (
                f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]} "
                f"{t_str[:2]}:{t_str[2:4]}:{t_str[4:6]}"
            )
    return ""
