from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_config, get_data_provider, get_policy, get_policy_engine
from packages.core.config import AppConfig
from packages.core.models import ScanResult
from packages.core.orchestrator import ScanOrchestrator
from packages.policy.engine import PolicyEngine
from packages.policy.schema import MergedPolicy
from packages.providers.base import BaseProvider
from packages.skills.reporting import generate_markdown_report
from packages.skills.tradingview_export import generate_watchlist_comma, generate_watchlist_csv

router = APIRouter()

# In-memory storage for MVP
_scan_results: dict[str, ScanResult] = {}
_latest_run_id: str | None = None
_latest_strategy_run_ids: dict[str, str] = {}


@router.post("/scan/run")
async def run_scan(
    config: AppConfig = Depends(get_config),
    policy: MergedPolicy = Depends(get_policy),
    provider: BaseProvider = Depends(get_data_provider),
    engine: PolicyEngine = Depends(get_policy_engine),
) -> dict[str, Any]:
    """Trigger a new scan run."""
    global _latest_run_id

    orchestrator = ScanOrchestrator(
        config=config,
        provider=provider,
        policy=policy,
        policy_engine=engine,
    )

    result = await orchestrator.run()
    _scan_results[result.meta.run_id] = result
    _latest_run_id = result.meta.run_id

    return {
        "run_id": result.meta.run_id,
        "tickers_scanned": result.meta.tickers_scanned,
        "setups_found": result.meta.setups_found,
        "setups_passed_risk": result.meta.setups_passed_risk,
        "cash_is_position": result.cash_is_position,
    }


@router.post("/scan/ticker/{symbol}")
async def scan_ticker(
    symbol: str,
    config: AppConfig = Depends(get_config),
    policy: MergedPolicy = Depends(get_policy),
    provider: BaseProvider = Depends(get_data_provider),
    engine: PolicyEngine = Depends(get_policy_engine),
) -> dict[str, Any]:
    """Scan a single ticker on demand."""
    global _latest_run_id

    orchestrator = ScanOrchestrator(
        config=config,
        provider=provider,
        policy=policy,
        policy_engine=engine,
    )

    result = await orchestrator.run_single(symbol)
    _scan_results[result.meta.run_id] = result
    _latest_run_id = result.meta.run_id

    return {
        "run_id": result.meta.run_id,
        "tickers_scanned": result.meta.tickers_scanned,
        "setups_found": result.meta.setups_found,
        "setups_passed_risk": result.meta.setups_passed_risk,
        "cash_is_position": result.cash_is_position,
    }


@router.get("/scan/latest")
async def get_latest_scan(
    config: AppConfig = Depends(get_config),
) -> dict[str, Any]:
    """Get the most recent scan result."""
    if _latest_run_id is None or _latest_run_id not in _scan_results:
        raise HTTPException(status_code=404, detail="No scan results available")

    result = _scan_results[_latest_run_id]
    return _serialize_scan_result(result, config)


@router.post("/scan/strategy/{strategy_name}")
async def run_strategy_scan(
    strategy_name: str,
    config: AppConfig = Depends(get_config),
    policy: MergedPolicy = Depends(get_policy),
    provider: BaseProvider = Depends(get_data_provider),
    engine: PolicyEngine = Depends(get_policy_engine),
) -> dict[str, Any]:
    """Trigger a strategy-specific scan (swing or position)."""
    if strategy_name not in ("swing", "position"):
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy_name}")

    orchestrator = ScanOrchestrator(
        config=config, provider=provider, policy=policy, policy_engine=engine,
    )

    result = await orchestrator.run_strategy(strategy_name)
    _scan_results[result.meta.run_id] = result
    _latest_strategy_run_ids[strategy_name] = result.meta.run_id

    return {
        "run_id": result.meta.run_id,
        "strategy": strategy_name,
        "tickers_scanned": result.meta.tickers_scanned,
        "setups_found": result.meta.setups_found,
        "setups_passed_risk": result.meta.setups_passed_risk,
        "cash_is_position": result.cash_is_position,
    }


@router.get("/scan/strategy/{strategy_name}/latest")
async def get_latest_strategy_scan(
    strategy_name: str,
    config: AppConfig = Depends(get_config),
) -> dict[str, Any]:
    """Get the most recent result for a strategy."""
    if strategy_name not in ("swing", "position"):
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy_name}")

    run_id = _latest_strategy_run_ids.get(strategy_name)
    if run_id is None or run_id not in _scan_results:
        raise HTTPException(
            status_code=404,
            detail=f"No {strategy_name} scan results available",
        )

    return _serialize_scan_result(_scan_results[run_id], config)


@router.get("/scan/{run_id}")
async def get_scan_by_id(
    run_id: str,
    config: AppConfig = Depends(get_config),
) -> dict[str, Any]:
    """Get a specific scan result by run ID."""
    if run_id not in _scan_results:
        raise HTTPException(status_code=404, detail=f"Scan run {run_id} not found")

    return _serialize_scan_result(_scan_results[run_id], config)


@router.get("/export/tradingview")
async def export_tradingview() -> dict[str, str]:
    """Export latest scan as TradingView watchlist."""
    if _latest_run_id is None or _latest_run_id not in _scan_results:
        raise HTTPException(status_code=404, detail="No scan results available")

    result = _scan_results[_latest_run_id]
    return {
        "watchlist_csv": generate_watchlist_csv(result),
        "watchlist_comma": generate_watchlist_comma(result),
    }


def _serialize_scan_result(result: ScanResult, config: AppConfig) -> dict[str, Any]:
    """Serialize a ScanResult to a JSON-compatible dict."""
    return {
        "meta": {
            "run_id": result.meta.run_id,
            "started_at": result.meta.started_at.isoformat(),
            "completed_at": (
                result.meta.completed_at.isoformat() if result.meta.completed_at else None
            ),
            "tickers_scanned": result.meta.tickers_scanned,
            "setups_found": result.meta.setups_found,
            "setups_passed_risk": result.meta.setups_passed_risk,
        },
        "cash_is_position": result.cash_is_position,
        "banner_message": result.banner_message,
        "results": [
            {
                "rank": r.rank,
                "symbol": r.symbol,
                "direction": r.direction,
                "setup": {
                    "entry": str(r.setup.entry),
                    "stop": str(r.setup.stop),
                    "target_1": str(r.setup.target_1),
                    "target_2": str(r.setup.target_2) if r.setup.target_2 else None,
                    "rr_ratio": r.setup.rr_ratio,
                    "shares": r.setup.shares,
                    "dollar_risk": str(r.setup.dollar_risk),
                    "dollar_pnl_t1": str(r.setup.dollar_pnl_t1),
                },
                "score": {
                    "total": r.score.total,
                    "confluence": r.score.confluence,
                    "invalidation": r.score.invalidation,
                    "rr": r.score.rr,
                    "momentum": r.score.momentum,
                    "volume": r.score.volume,
                    "pattern": r.score.pattern,
                    "cleanliness": r.score.cleanliness,
                    "web_intel_modifier": r.score.web_intel_modifier,
                },
                "patterns": [
                    {"name": p.name, "direction": p.direction, "confidence": p.confidence}
                    for p in r.patterns
                ],
                "checklist": [
                    {
                        "criterion": c.criterion,
                        "passed": c.passed,
                        "value": c.value,
                        "notes": c.notes,
                    }
                    for c in r.checklist
                ],
                "basis": r.basis,
                "current_price": str(r.current_price) if r.current_price else None,
                "web_intel_notes": r.web_intel_notes,
            }
            for r in result.results
        ],
        "report_markdown": generate_markdown_report(result, language=config.output.language),
    }
