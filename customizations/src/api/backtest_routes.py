"""Backtest Web API routes for the backtest dashboard and direct execution.

All routes require authentication via ``require_auth``.
Follows the existing ``register_xxx_routes(app, require_auth=None)`` pattern
used by ``src.usage.admin_routes``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Safe run_id characters (prevents path traversal in /backtest/runs/{run_id}/...).
_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class BacktestRunRequest(BaseModel):
    """Body for POST /backtest/run — execute a direct backtest."""

    strategy_id: str
    codes: list[str]
    start_date: str
    end_date: str
    params: dict = Field(default_factory=dict)
    source: str = "akshare"
    initial_cash: float = 1_000_000
    interval: str = "1D"
    generate_chart: bool = True


class CustomBacktestRequest(BaseModel):
    """Body for POST /backtest/custom — natural-language backtest via session agent."""

    prompt: str
    codes: list[str] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""


# --------------------------------------------------------------------------- #
# Route registration
# --------------------------------------------------------------------------- #
def register_backtest_routes(app: FastAPI, require_auth: Any = None) -> None:
    """Mount /backtest/* routes onto the FastAPI app."""

    if require_auth is None:
        import sys as _sys
        _host = _sys.modules.get("api_server")
        if _host is not None:
            require_auth = getattr(_host, "require_auth", None)
        if require_auth is None:
            # Fallback: allow all if no auth configured (dev mode)
            def require_auth():  # type: ignore[no-redef]
                return None

    # ================================================================
    # Dashboard (HTML)
    # ================================================================
    @app.get("/backtest/dashboard", dependencies=[Depends(require_auth)])
    async def backtest_dashboard():
        from src.backtest.dashboard import get_backtest_dashboard_html
        return HTMLResponse(content=get_backtest_dashboard_html())

    # ================================================================
    # Strategy templates
    # ================================================================
    @app.get("/backtest/strategies", dependencies=[Depends(require_auth)])
    async def list_backtest_strategies():
        from src.backtest.templates import list_strategies
        try:
            return list_strategies()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to list backtest strategies")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/backtest/strategies/{strategy_id}", dependencies=[Depends(require_auth)])
    async def get_backtest_strategy(strategy_id: str):
        from src.backtest.templates import get_strategy
        try:
            strategy = get_strategy(strategy_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to fetch strategy %s", strategy_id)
            raise HTTPException(status_code=500, detail=str(exc))
        if not strategy:
            raise HTTPException(
                status_code=404,
                detail=f"Strategy '{strategy_id}' not found",
            )
        return strategy

    # ================================================================
    # Run a direct backtest (sync work off-loaded to executor)
    # ================================================================
    @app.post("/backtest/run", dependencies=[Depends(require_auth)])
    async def run_backtest(req: BacktestRunRequest):
        from src.backtest.direct_runner import run_direct_backtest

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: run_direct_backtest(
                    strategy_id=req.strategy_id,
                    codes=list(req.codes),
                    start_date=req.start_date,
                    end_date=req.end_date,
                    params=dict(req.params),
                    source=req.source,
                    initial_cash=req.initial_cash,
                    interval=req.interval,
                    generate_chart=req.generate_chart,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Direct backtest failed for %s", req.strategy_id)
            raise HTTPException(status_code=500, detail=str(exc))

        if isinstance(result, dict):
            returncode = _coerce_int(result.get("returncode"), default=0)
            status = str(result.get("status", "") or "").lower()
            if returncode != 0 or status in ("error", "failed", "failure"):
                detail = result.get("stderr") or result.get("error") or "backtest failed"
                raise HTTPException(status_code=500, detail=str(detail))
        return result

    # ================================================================
    # Run artifacts
    # ================================================================
    @app.get("/backtest/runs/{run_id}/chart", dependencies=[Depends(require_auth)])
    async def get_backtest_run_chart(run_id: str):
        from src.api.helpers import RUNS_DIR

        _validate_run_id(run_id)
        chart_path = RUNS_DIR / run_id / "artifacts" / "chart.png"
        if not chart_path.exists() or not chart_path.is_file():
            raise HTTPException(status_code=404, detail="Chart not found for this run")
        return FileResponse(str(chart_path), media_type="image/png")

    @app.get("/backtest/runs", dependencies=[Depends(require_auth)])
    async def list_backtest_runs(limit: int = 50):
        """List recent backtest runs sorted by run_id (newest first)."""
        from src.api.helpers import RUNS_DIR

        limit = min(max(1, limit), 200)
        if not RUNS_DIR.exists():
            return []

        run_dirs = sorted(
            [d for d in RUNS_DIR.iterdir() if d.is_dir()],
            key=lambda x: x.name,
            reverse=True,
        )

        results = []
        for d in run_dirs[:limit]:
            run_id = d.name
            state = _load_json(d / "state.json")
            config = _load_json(d / "config.json")

            status = str(state.get("status") or "").lower() or "unknown"
            if not state and (d / "artifacts" / "equity.csv").exists():
                status = "success"

            strategy = (
                config.get("strategy")
                or config.get("strategy_name")
                or ""
            )
            codes = _extract_codes(config)
            start_date = config.get("start_date", "")
            end_date = config.get("end_date", "")
            created_at = _parse_created_at(run_id, d)

            results.append(
                {
                    "run_id": run_id,
                    "status": status,
                    "strategy": strategy,
                    "codes": codes,
                    "start_date": start_date,
                    "end_date": end_date,
                    "created_at": created_at,
                }
            )
        return results

    # ================================================================
    # Natural-language backtest via the session agent
    # ================================================================
    @app.post("/backtest/custom", dependencies=[Depends(require_auth)])
    async def custom_backtest(req: CustomBacktestRequest):
        prompt = req.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="prompt is required")

        from src.api.state import _get_session_service
        svc = _get_session_service()
        if svc is None:
            raise HTTPException(
                status_code=503,
                detail="Session runtime not enabled",
            )

        # Enrich the prompt with the optional scope context.
        ctx_parts: list[str] = []
        if req.codes:
            ctx_parts.append("标的: " + ", ".join(req.codes))
        if req.start_date:
            ctx_parts.append("开始日期: " + req.start_date)
        if req.end_date:
            ctx_parts.append("结束日期: " + req.end_date)
        full_prompt = prompt
        if ctx_parts:
            full_prompt = prompt + "\n\n" + "\n".join(ctx_parts)

        try:
            session = svc.create_session(
                title=f"backtest: {prompt[:40]}",
                config={"channel": "api", "backtest": True},
            )
            result = await svc.send_message(
                session.session_id,
                full_prompt,
                sender_id="api",
                channel="api",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Custom backtest session failed")
            raise HTTPException(status_code=500, detail=str(exc))

        return {
            "session_id": session.session_id,
            "attempt_id": result.get("attempt_id") if isinstance(result, dict) else None,
        }


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #
def _validate_run_id(run_id: str) -> None:
    """Reject run_id values that could escape the runs directory."""
    if not run_id or not _SAFE_RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id")


def _coerce_int(val, *, default: int = 0) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _load_json(path) -> dict:
    """Read a JSON file, returning an empty dict on any error."""
    import json

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _extract_codes(config: dict) -> list[str]:
    """Pull the codes list out of a run config.json (several key spellings)."""
    for key in ("codes", "symbols", "universe"):
        val = config.get(key)
        if not val:
            continue
        if isinstance(val, (list, tuple)):
            return [str(c) for c in val]
        return [str(val)]
    return []


def _parse_created_at(run_id: str, run_dir) -> str:
    """Parse a creation timestamp from a run_id, falling back to mtime.

    Supports ``YYYYMMDD_HHMMSS`` and ``run_YYYYMMDD_HHMMSS`` styles.
    """
    parts = run_id.split("_")
    d_str = t_str = ""
    if run_id.startswith("run_") and len(parts) >= 3:
        d_str, t_str = parts[1], parts[2]
    elif len(parts) >= 2:
        d_str, t_str = parts[0], parts[1]

    if len(d_str) == 8 and len(t_str) == 6:
        return (
            f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]} "
            f"{t_str[:2]}:{t_str[2:4]}:{t_str[4:6]}"
        )

    try:
        mtime = datetime.fromtimestamp(run_dir.stat().st_mtime)
        return mtime.strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError):
        return "Unknown"
