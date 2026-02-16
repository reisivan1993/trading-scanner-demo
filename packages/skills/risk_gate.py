from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd

from packages.core.models import TradeSetup
from packages.skills.base import BaseSkill


@dataclass(frozen=True)
class RiskGateResult:
    passed: bool
    reason: str = ""


def check_min_rr(setup: TradeSetup, min_rr: float) -> RiskGateResult:
    """Check minimum reward-to-risk ratio."""
    if setup.rr_ratio < min_rr:
        return RiskGateResult(False, f"RR {setup.rr_ratio:.2f} below minimum {min_rr}")
    return RiskGateResult(True)


def check_stop_validation(setup: TradeSetup, max_stop_pct: float | None = None) -> RiskGateResult:
    """Validate stop placement."""
    if setup.entry == 0:
        return RiskGateResult(False, "Entry price is zero")

    stop_pct = abs(float(setup.entry - setup.stop) / float(setup.entry)) * 100

    if max_stop_pct is not None and stop_pct > max_stop_pct:
        return RiskGateResult(
            False,
            f"Stop distance {stop_pct:.1f}% exceeds max {max_stop_pct}%",
        )

    return RiskGateResult(True)


def check_dollar_volume(
    avg_dollar_volume: float,
    min_dollar_volume: float,
) -> RiskGateResult:
    """Check minimum average dollar volume."""
    if avg_dollar_volume < min_dollar_volume:
        return RiskGateResult(
            False,
            f"Avg dollar volume ${avg_dollar_volume:,.0f} below ${min_dollar_volume:,.0f}",
        )
    return RiskGateResult(True)


def check_penny_stock(price: Decimal, allow_penny: bool, min_price: float) -> RiskGateResult:
    """Check if stock is a penny stock."""
    if not allow_penny and float(price) < min_price:
        return RiskGateResult(False, f"Price ${price} below minimum ${min_price}")
    return RiskGateResult(True)


def check_max_stop_dollars(
    setup: TradeSetup,
    max_stop_dollars: float | None = None,
) -> RiskGateResult:
    """Check maximum dollar risk per share (advanced policy)."""
    if max_stop_dollars is None:
        return RiskGateResult(True)

    per_share_risk = abs(float(setup.entry - setup.stop))
    if per_share_risk > max_stop_dollars:
        return RiskGateResult(
            False,
            f"Per-share risk ${per_share_risk:.2f} exceeds max ${max_stop_dollars:.2f}",
        )
    return RiskGateResult(True)


def check_short_squeeze_penalty(
    direction: str,
    rvol: float | None = None,
    min_rvol_short: float | None = None,
) -> RiskGateResult:
    """Penalize shorts without sufficient relative volume."""
    if direction != "short" or min_rvol_short is None or rvol is None:
        return RiskGateResult(True)

    if rvol < min_rvol_short:
        return RiskGateResult(
            False,
            f"Short RVOL {rvol:.2f} below minimum {min_rvol_short}",
        )
    return RiskGateResult(True)


def run_risk_gate(
    setup: TradeSetup,
    *,
    min_rr: float = 2.0,
    max_stop_pct: float | None = None,
    avg_dollar_volume: float = 50_000_000,
    min_dollar_volume: float = 20_000_000,
    allow_penny: bool = False,
    min_price: float = 2.0,
    max_stop_dollars: float | None = None,
    rvol: float | None = None,
    min_rvol_short: float | None = None,
) -> RiskGateResult:
    """Run all risk gate checks. Returns first failure or pass."""
    checks = [
        check_min_rr(setup, min_rr),
        check_stop_validation(setup, max_stop_pct),
        check_dollar_volume(avg_dollar_volume, min_dollar_volume),
        check_penny_stock(setup.entry, allow_penny, min_price),
        check_max_stop_dollars(setup, max_stop_dollars),
        check_short_squeeze_penalty(setup.direction, rvol, min_rvol_short),
    ]

    for result in checks:
        if not result.passed:
            return result

    return RiskGateResult(True)


class RiskGateSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "risk_gate"

    def analyze(self, df: pd.DataFrame, **kwargs: Any) -> RiskGateResult:
        setup = kwargs["setup"]
        return run_risk_gate(setup, **{k: v for k, v in kwargs.items() if k != "setup"})
