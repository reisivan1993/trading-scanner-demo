from __future__ import annotations

from dataclasses import dataclass

from packages.core.config import AppConfig
from packages.policy.engine import PolicyEngine
from packages.policy.loader import deep_merge, load_policies
from packages.policy.schema import MergedPolicy


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


def test_deep_merge_nested_dicts() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": 10}
    override = {"a": {"z": 3}}
    result = deep_merge(base, override)
    assert result == {"a": {"x": 1, "y": 2, "z": 3}, "b": 10}


def test_deep_merge_override_wins() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": 10}
    override = {"a": {"x": 99}, "b": 42}
    result = deep_merge(base, override)
    assert result["a"]["x"] == 99
    assert result["a"]["y"] == 2
    assert result["b"] == 42


# ---------------------------------------------------------------------------
# load_policies
# ---------------------------------------------------------------------------


def test_load_policies_merges_all_layers() -> None:
    """Load the real YAML files and verify the merged result."""
    config = AppConfig(
        policy={
            "default_file": "policies/default.yml",
            "user_override_file": "policies/user_overrides.yml",
            "advanced_override_file": "policies/user_overrides_advanced.yml",
            "enable_advanced": True,
        }
    )
    policy = load_policies(config)

    # user_overrides overwrites default values
    assert policy.output.language == "he"
    assert policy.output.report_verbosity == "short"
    assert policy.universe.min_price == 10.0
    assert policy.universe.min_avg_dollar_volume_20d == 50_000_000
    assert policy.risk_gate.min_rr == 2.5
    assert policy.risk_gate.max_stop_pct_of_price == 4.0

    # default values that were not overridden
    assert policy.output.include_momentum_only_list is True
    assert policy.output.tradingview_export is True

    # advanced overrides
    assert policy.risk_gate_extensions.max_stop_dollars == 250.0
    assert policy.risk_gate_extensions.require_stop_near_structure is True
    assert policy.short_rules.require_breakdown_confirmation is True
    assert policy.short_rules.min_rvol == 1.6
    assert policy.long_rules.max_distance_from_support_atr == 1.2
    assert policy.output_extensions.momentum_only_min_score == 65

    # exclude_gap_days from user_overrides
    assert policy.universe.exclude_gap_days.enabled is True
    assert policy.universe.exclude_gap_days.gap_pct_threshold == 5.0


# ---------------------------------------------------------------------------
# PolicyEngine.pre_filter_universe
# ---------------------------------------------------------------------------


@dataclass
class _StubTicker:
    symbol: str
    price: float
    avg_dollar_volume_20d: float
    gap_pct: float | None = None


def test_policy_engine_pre_filter_universe() -> None:
    engine = PolicyEngine()
    policy = MergedPolicy(universe={"min_price": 5.0, "min_avg_dollar_volume_20d": 1_000_000})

    items = [
        _StubTicker("AAPL", price=150.0, avg_dollar_volume_20d=5_000_000),
        _StubTicker("PENNY", price=1.50, avg_dollar_volume_20d=5_000_000),  # below min_price
        _StubTicker("LOW_VOL", price=20.0, avg_dollar_volume_20d=500_000),  # below volume
        _StubTicker("GAPPED", price=30.0, avg_dollar_volume_20d=2_000_000, gap_pct=6.0),
    ]

    result = engine.pre_filter_universe(items, policy)

    # Without gap exclusion enabled, GAPPED should still pass
    symbols = [r.symbol for r in result]
    assert "AAPL" in symbols
    assert "PENNY" not in symbols
    assert "LOW_VOL" not in symbols
    assert "GAPPED" in symbols


def test_policy_engine_pre_filter_universe_excludes_gap_days() -> None:
    engine = PolicyEngine()
    policy = MergedPolicy(
        universe={
            "min_price": 5.0,
            "min_avg_dollar_volume_20d": 1_000_000,
            "exclude_gap_days": {"enabled": True, "gap_pct_threshold": 5.0},
        }
    )

    items = [
        _StubTicker("AAPL", price=150.0, avg_dollar_volume_20d=5_000_000),
        _StubTicker("GAPPED", price=30.0, avg_dollar_volume_20d=2_000_000, gap_pct=6.0),
    ]

    result = engine.pre_filter_universe(items, policy)
    symbols = [r.symbol for r in result]
    assert "AAPL" in symbols
    assert "GAPPED" not in symbols


# ---------------------------------------------------------------------------
# Schema defaults
# ---------------------------------------------------------------------------


def test_schema_defaults() -> None:
    policy = MergedPolicy()

    assert policy.version == 1
    assert policy.output.language == "en"
    assert policy.output.report_verbosity == "medium"
    assert policy.universe.min_price == 2.0
    assert policy.universe.min_avg_dollar_volume_20d == 20_000_000
    assert policy.universe.exclude_gap_days.enabled is False
    assert policy.risk_gate.min_rr == 2.0
    assert policy.risk_gate.target_profit_min == 500.0
    assert policy.risk_gate_extensions.require_stop_near_structure is False
    assert policy.short_rules.require_breakdown_confirmation is False
    assert policy.long_rules.max_distance_from_support_atr is None
    assert policy.output_extensions.momentum_only_min_score is None
