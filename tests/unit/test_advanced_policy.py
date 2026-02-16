from __future__ import annotations

from decimal import Decimal

import pytest

from packages.core.config import AppConfig, PolicyPathsConfig
from packages.core.models import TradeSetup
from packages.policy.engine import PolicyEngine
from packages.policy.loader import deep_merge, load_policies
from packages.policy.schema import (
    LongRules,
    MarketStructureFilters,
    MergedPolicy,
    OutputExtensions,
    RiskGateExtensions,
    ShortRules,
)
from packages.skills.risk_gate import check_max_stop_dollars, check_short_squeeze_penalty


def _make_setup(**kwargs) -> TradeSetup:
    defaults = dict(
        symbol="AAPL", direction="long",
        entry=Decimal("170.00"), stop=Decimal("167.00"),
        target_1=Decimal("176.00"), target_2=Decimal("179.00"),
        rr_ratio=2.0, shares=58,
        dollar_risk=Decimal("174.00"),
        dollar_pnl_t1=Decimal("348.00"), dollar_pnl_t2=Decimal("522.00"),
    )
    defaults.update(kwargs)
    return TradeSetup(**defaults)


class TestAdvancedPolicyLoading:
    def test_load_with_advanced_enabled(self) -> None:
        config = AppConfig(policy=PolicyPathsConfig(enable_advanced=True))
        policy = load_policies(config)
        assert policy.risk_gate_extensions.max_stop_dollars == 250.0
        assert policy.short_rules.require_breakdown_confirmation is True

    def test_load_without_advanced(self) -> None:
        config = AppConfig(policy=PolicyPathsConfig(enable_advanced=False))
        policy = load_policies(config)
        assert policy.risk_gate_extensions.max_stop_dollars is None
        assert policy.short_rules.require_breakdown_confirmation is False


class TestRiskGateExtensions:
    def test_max_stop_dollars_passes(self) -> None:
        setup = _make_setup(entry=Decimal("170.00"), stop=Decimal("169.00"))
        result = check_max_stop_dollars(setup, max_stop_dollars=250.0)
        assert result.passed

    def test_max_stop_dollars_rejects(self) -> None:
        setup = _make_setup(entry=Decimal("500.00"), stop=Decimal("200.00"))
        result = check_max_stop_dollars(setup, max_stop_dollars=250.0)
        assert not result.passed


class TestShortRules:
    def test_short_rvol_check(self) -> None:
        result = check_short_squeeze_penalty("short", rvol=2.0, min_rvol_short=1.6)
        assert result.passed

    def test_short_rvol_too_low(self) -> None:
        result = check_short_squeeze_penalty("short", rvol=1.0, min_rvol_short=1.6)
        assert not result.passed


class TestMarketStructureFilters:
    def test_wick_ratio_max_schema(self) -> None:
        policy = MergedPolicy(
            market_structure_filters=MarketStructureFilters(wick_ratio_max=2.2)
        )
        assert policy.market_structure_filters.wick_ratio_max == 2.2


class TestOutputExtensions:
    def test_momentum_only_min_score(self) -> None:
        policy = MergedPolicy(
            output_extensions=OutputExtensions(momentum_only_min_score=65)
        )
        assert policy.output_extensions.momentum_only_min_score == 65
