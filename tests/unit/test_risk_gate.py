from __future__ import annotations

from decimal import Decimal

import pytest

from packages.core.models import TradeSetup
from packages.skills.risk_gate import (
    check_dollar_volume,
    check_min_rr,
    check_penny_stock,
    check_short_squeeze_penalty,
    check_stop_validation,
    run_risk_gate,
)


def _make_setup(
    entry: float = 170.0,
    stop: float = 167.0,
    target_1: float = 176.0,
    rr: float = 2.0,
    direction: str = "long",
) -> TradeSetup:
    return TradeSetup(
        symbol="AAPL",
        direction=direction,
        entry=Decimal(str(entry)),
        stop=Decimal(str(stop)),
        target_1=Decimal(str(target_1)),
        target_2=Decimal(str(target_1 + 3)),
        rr_ratio=rr,
        shares=58,
        dollar_risk=Decimal("174.00"),
        dollar_pnl_t1=Decimal("348.00"),
        dollar_pnl_t2=Decimal("522.00"),
    )


class TestCheckMinRR:
    def test_rr_above_min_passes(self) -> None:
        result = check_min_rr(_make_setup(rr=3.0), 2.0)
        assert result.passed

    def test_rr_below_min_rejects(self) -> None:
        result = check_min_rr(_make_setup(rr=1.5), 2.0)
        assert not result.passed
        assert "below minimum" in result.reason


class TestCheckStopValidation:
    def test_stop_within_limit_passes(self) -> None:
        result = check_stop_validation(_make_setup(), max_stop_pct=5.0)
        assert result.passed

    def test_stop_exceeds_limit_rejects(self) -> None:
        setup = _make_setup(entry=100.0, stop=90.0)
        result = check_stop_validation(setup, max_stop_pct=5.0)
        assert not result.passed


class TestCheckDollarVolume:
    def test_sufficient_volume_passes(self) -> None:
        result = check_dollar_volume(50_000_000, 20_000_000)
        assert result.passed

    def test_insufficient_volume_rejects(self) -> None:
        result = check_dollar_volume(10_000_000, 20_000_000)
        assert not result.passed


class TestCheckPennyStock:
    def test_normal_stock_passes(self) -> None:
        result = check_penny_stock(Decimal("170.00"), False, 2.0)
        assert result.passed

    def test_penny_stock_rejects(self) -> None:
        result = check_penny_stock(Decimal("1.50"), False, 2.0)
        assert not result.passed

    def test_penny_stock_allowed(self) -> None:
        result = check_penny_stock(Decimal("1.50"), True, 2.0)
        assert result.passed


class TestShortSqueezePenalty:
    def test_short_with_high_rvol_passes(self) -> None:
        result = check_short_squeeze_penalty("short", rvol=2.0, min_rvol_short=1.6)
        assert result.passed

    def test_short_with_low_rvol_rejects(self) -> None:
        result = check_short_squeeze_penalty("short", rvol=1.0, min_rvol_short=1.6)
        assert not result.passed

    def test_long_always_passes(self) -> None:
        result = check_short_squeeze_penalty("long", rvol=0.5, min_rvol_short=1.6)
        assert result.passed


class TestRunRiskGate:
    def test_all_checks_pass(self) -> None:
        result = run_risk_gate(_make_setup(rr=3.0), min_rr=2.0)
        assert result.passed

    def test_fails_on_first_check(self) -> None:
        result = run_risk_gate(_make_setup(rr=1.0), min_rr=2.0)
        assert not result.passed
