from __future__ import annotations

import structlog
from decimal import Decimal
from typing import Any

from src.risk.models import Setup

logger = structlog.get_logger()


def apply_risk_gate(
    setup: Setup,
    policy: dict[str, Any],
    position_size_usd: Decimal,
) -> bool:
    """Return True if setup passes all risk gate checks, False otherwise.

    All thresholds come from the resolved policy, never hardcoded.
    """
    risk_gate = policy.get("risk_gate", {})
    log = logger.bind(ticker=setup.ticker, direction=setup.direction.value)

    min_rr = Decimal(str(risk_gate.get("min_rr", "2.0")))
    if setup.rr_ratio < min_rr:
        log.info("risk_gate.rejected", rule="min_rr", rr=str(setup.rr_ratio), min_rr=str(min_rr))
        return False

    profit = setup.expected_profit(position_size_usd)
    min_profit = Decimal(str(risk_gate.get("target_profit_min", "500")))
    max_profit = Decimal(str(risk_gate.get("target_profit_max", "1000")))
    if profit < min_profit:
        log.info("risk_gate.rejected", rule="profit_too_low", profit=str(profit))
        return False
    if profit > max_profit:
        log.info("risk_gate.skipped_cap", rule="profit_cap", profit=str(profit))

    max_stop_pct = risk_gate.get("max_stop_pct_of_price")
    if max_stop_pct is not None:
        stop_pct = (setup.risk_per_share / setup.entry) * 100 if setup.entry else Decimal("0")
        if stop_pct > Decimal(str(max_stop_pct)):
            log.info("risk_gate.rejected", rule="stop_pct", stop_pct=str(stop_pct))
            return False

    log.info("risk_gate.passed", rr=str(setup.rr_ratio), profit=str(profit))
    return True
