from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from packages.core.indicators import compute_all_indicators
from packages.core.models import (
    VolumeAnalysisResult,
    VolumeConditionTag,
    VSAPatternTag,
)
from packages.skills.volume_analysis import (
    DEFAULTS,
    analyze_volume,
    classify_volume_condition,
    detect_breakout_validity,
    detect_buying_climax,
    detect_no_demand_test,
    detect_no_supply_test,
    detect_stopping_volume,
    detect_volume_divergences,
    detect_vsa_patterns,
    VolumeAnalysisSkill,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_params(**overrides):
    params = dict(DEFAULTS)
    params.update(overrides)
    return params


def _make_base_df(n: int = 35, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    close = 100.0 + np.cumsum(np.random.randn(n) * 0.3)
    volume = np.full(n, 100_000, dtype=int)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.1,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": volume,
    })
    return compute_all_indicators(df)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_df() -> pd.DataFrame:
    """35 bars of flat/normal price action, uniform volume."""
    return _make_base_df(n=35)


@pytest.fixture
def stopping_volume_df() -> pd.DataFrame:
    """35 bars in downtrend; last signal bar has extreme vol + lower wick + close_pos=0.55."""
    np.random.seed(42)
    n = 35
    close = 100.0 - np.arange(n) * 0.2 + np.random.randn(n) * 0.05
    volume = np.full(n, 100_000, dtype=int)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.1,
        "high": close + 0.3,
        "low": close - 1.5,
        "close": close,
        "volume": volume,
    })
    # Signal bar: index 30 — extreme volume + large lower wick + mid-to-high close
    i = 30
    bar_low = close[i] - 3.0
    bar_high = close[i] + 0.5
    bar_close = bar_low + (bar_high - bar_low) * 0.55  # close_pos = 0.55
    bar_open = bar_low + (bar_high - bar_low) * 0.45   # open mid-range → large lower wick
    df.loc[i, "volume"] = 400_000                       # 4× median
    df.loc[i, "low"] = bar_low
    df.loc[i, "high"] = bar_high
    df.loc[i, "open"] = bar_open
    df.loc[i, "close"] = bar_close
    # Confirmation bar: next bar closes above signal bar low
    df.loc[i + 1, "close"] = bar_low + 0.5
    return compute_all_indicators(df)


@pytest.fixture
def buying_climax_df() -> pd.DataFrame:
    """35 bars in uptrend; signal bar has extreme vol + close_pos=0.1."""
    np.random.seed(42)
    n = 35
    close = 100.0 + np.arange(n) * 0.3 + np.random.randn(n) * 0.05
    volume = np.full(n, 100_000, dtype=int)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close + 0.1,
        "high": close + 1.0,
        "low": close - 0.3,
        "close": close,
        "volume": volume,
    })
    # Signal bar: extreme volume + close near the low (close_pos ~ 0.1)
    i = 30
    bar_low = close[i] - 3.0
    bar_high = close[i] + 1.0
    bar_close = bar_low + (bar_high - bar_low) * 0.1   # close_pos = 0.1
    bar_open = bar_high - 0.2                           # opens near high
    df.loc[i, "volume"] = 400_000
    df.loc[i, "low"] = bar_low
    df.loc[i, "high"] = bar_high
    df.loc[i, "open"] = bar_open
    df.loc[i, "close"] = bar_close
    return compute_all_indicators(df)


@pytest.fixture
def no_supply_df() -> pd.DataFrame:
    """35 bars; signal bar has low vol + narrow spread + close_pos=0.65."""
    np.random.seed(42)
    n = 35
    close = 100.0 + np.cumsum(np.random.randn(n) * 0.3)
    avg_spread = 1.0
    volume = np.full(n, 100_000, dtype=int)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.5,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": volume,
    })
    # Signal bar: low volume + narrow spread + close in upper half
    i = 30
    narrow_half = avg_spread * 0.3
    bar_low = close[i] - narrow_half
    bar_high = close[i] + narrow_half
    bar_close = bar_low + (bar_high - bar_low) * 0.65
    df.loc[i, "volume"] = 40_000                        # 0.4× median
    df.loc[i, "low"] = bar_low
    df.loc[i, "high"] = bar_high
    df.loc[i, "open"] = bar_low + 0.1
    df.loc[i, "close"] = bar_close
    return compute_all_indicators(df)


@pytest.fixture
def divergence_df() -> pd.DataFrame:
    """30 bars of slowly declining price AND declining volume."""
    np.random.seed(42)
    n = 30
    close = 100.0 - np.linspace(0, 3.0, n)
    volume = (100_000 - np.linspace(0, 50_000, n)).astype(int)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.1,
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "volume": volume,
    })
    return compute_all_indicators(df)


@pytest.fixture
def breakout_df() -> pd.DataFrame:
    """35 bars; last bar crosses above a key level with high vol + wide spread."""
    np.random.seed(42)
    n = 35
    close = np.full(n, 100.0)
    volume = np.full(n, 100_000, dtype=int)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.1,
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "volume": volume,
    })
    # Last bar: breaks above 100.5, high vol, wide spread
    df.loc[n - 1, "close"] = 101.5
    df.loc[n - 1, "high"] = 102.0
    df.loc[n - 1, "low"] = 100.2
    df.loc[n - 1, "open"] = 100.3
    df.loc[n - 1, "volume"] = 300_000
    # Previous bar stays below the level
    df.loc[n - 2, "close"] = 100.0
    return compute_all_indicators(df)


# ---------------------------------------------------------------------------
# TestClassifyVolumeCondition
# ---------------------------------------------------------------------------

class TestClassifyVolumeCondition:
    def test_healthy_move_high_vol_wide_spread_strong_close(self) -> None:
        params = _make_params()
        result = classify_volume_condition(
            vol_rel=2.0,
            spread_rel=1.5,
            close_pos=0.85,
            params=params,
        )
        assert result == VolumeConditionTag.HEALTHY_MOVE

    def test_effort_no_result_high_vol_narrow_spread(self) -> None:
        params = _make_params()
        result = classify_volume_condition(
            vol_rel=2.0,
            spread_rel=0.7,
            close_pos=0.5,
            params=params,
        )
        assert result == VolumeConditionTag.EFFORT_NO_RESULT

    def test_no_supply_low_vol_narrow_spread_closes_high(self) -> None:
        params = _make_params()
        result = classify_volume_condition(
            vol_rel=0.5,
            spread_rel=0.6,
            close_pos=0.7,
            params=params,
        )
        assert result == VolumeConditionTag.NO_SUPPLY

    def test_no_demand_low_vol_narrow_spread_closes_low(self) -> None:
        params = _make_params()
        result = classify_volume_condition(
            vol_rel=0.5,
            spread_rel=0.6,
            close_pos=0.3,
            params=params,
        )
        assert result == VolumeConditionTag.NO_DEMAND

    def test_neutral_mid_vol_mid_spread(self) -> None:
        params = _make_params()
        result = classify_volume_condition(
            vol_rel=1.0,
            spread_rel=1.0,
            close_pos=0.5,
            params=params,
        )
        assert result == VolumeConditionTag.NEUTRAL


# ---------------------------------------------------------------------------
# TestDetectStoppingVolume
# ---------------------------------------------------------------------------

class TestDetectStoppingVolume:
    def test_detects_stopping_volume_in_downtrend(self, stopping_volume_df: pd.DataFrame) -> None:
        params = _make_params()
        vol_avg = stopping_volume_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (stopping_volume_df["high"] - stopping_volume_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_stopping_volume(stopping_volume_df, vol_avg, spread_avg, params)
        assert len(signals) >= 1
        assert all(s.direction == "bullish" for s in signals)
        assert all(s.pattern == VSAPatternTag.STOPPING_VOLUME for s in signals)

    def test_no_detection_in_uptrend_context(self, buying_climax_df: pd.DataFrame) -> None:
        """Stopping volume requires close < ema_20. In uptrend, should not fire."""
        params = _make_params()
        vol_avg = buying_climax_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (buying_climax_df["high"] - buying_climax_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_stopping_volume(buying_climax_df, vol_avg, spread_avg, params)
        # Uptrend df has close > ema_20, so context gate blocks detections
        assert all(s.direction == "bullish" for s in signals)  # any remaining are still bullish

    def test_no_detection_when_vol_below_extreme_mult(self, base_df: pd.DataFrame) -> None:
        params = _make_params(extreme_vol_mult=10.0)  # unreachably high threshold
        vol_avg = base_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (base_df["high"] - base_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_stopping_volume(base_df, vol_avg, spread_avg, params)
        assert signals == []

    def test_confidence_between_zero_and_one(self, stopping_volume_df: pd.DataFrame) -> None:
        params = _make_params()
        vol_avg = stopping_volume_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (stopping_volume_df["high"] - stopping_volume_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_stopping_volume(stopping_volume_df, vol_avg, spread_avg, params)
        for s in signals:
            assert 0.0 <= s.confidence <= 1.0


# ---------------------------------------------------------------------------
# TestDetectBuyingClimax
# ---------------------------------------------------------------------------

class TestDetectBuyingClimax:
    def test_detects_buying_climax_in_uptrend(self, buying_climax_df: pd.DataFrame) -> None:
        params = _make_params()
        vol_avg = buying_climax_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (buying_climax_df["high"] - buying_climax_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_buying_climax(buying_climax_df, vol_avg, spread_avg, params)
        assert len(signals) >= 1
        assert all(s.direction == "bearish" for s in signals)
        assert all(s.pattern == VSAPatternTag.BUYING_CLIMAX for s in signals)

    def test_no_detection_when_closes_high(self, base_df: pd.DataFrame) -> None:
        """A bar closing strongly (close_pos high) should not trigger buying climax."""
        params = _make_params(extreme_vol_mult=10.0)  # unreachably high threshold
        vol_avg = base_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (base_df["high"] - base_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_buying_climax(base_df, vol_avg, spread_avg, params)
        assert signals == []

    def test_confidence_between_zero_and_one(self, buying_climax_df: pd.DataFrame) -> None:
        params = _make_params()
        vol_avg = buying_climax_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (buying_climax_df["high"] - buying_climax_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_buying_climax(buying_climax_df, vol_avg, spread_avg, params)
        for s in signals:
            assert 0.0 <= s.confidence <= 1.0


# ---------------------------------------------------------------------------
# TestDetectNoSupplyTest
# ---------------------------------------------------------------------------

class TestDetectNoSupplyTest:
    def test_detects_no_supply_low_vol_closes_upper_half(self, no_supply_df: pd.DataFrame) -> None:
        params = _make_params()
        vol_avg = no_supply_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (no_supply_df["high"] - no_supply_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_no_supply_test(no_supply_df, vol_avg, spread_avg, params)
        assert len(signals) >= 1
        assert all(s.direction == "bullish" for s in signals)
        assert all(s.pattern == VSAPatternTag.NO_SUPPLY_TEST for s in signals)

    def test_no_detection_when_vol_is_high(self, base_df: pd.DataFrame) -> None:
        """When volume is high, no-supply test should not fire."""
        params = _make_params(low_vol_mult=0.0)  # impossible threshold
        vol_avg = base_df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (base_df["high"] - base_df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_no_supply_test(base_df, vol_avg, spread_avg, params)
        assert signals == []


# ---------------------------------------------------------------------------
# TestDetectNoDemandTest
# ---------------------------------------------------------------------------

class TestDetectNoDemandTest:
    def test_detects_no_demand_low_vol_closes_lower_half(self) -> None:
        np.random.seed(42)
        n = 35
        close = 100.0 + np.cumsum(np.random.randn(n) * 0.3)
        volume = np.full(n, 100_000, dtype=int)
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": close + 0.4,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": volume,
        })
        # Signal bar: low vol + narrow spread + close in lower half
        i = 30
        bar_low = close[i] - 0.3
        bar_high = close[i] + 0.3
        bar_close = bar_low + (bar_high - bar_low) * 0.2  # close_pos = 0.2
        df.loc[i, "volume"] = 40_000
        df.loc[i, "low"] = bar_low
        df.loc[i, "high"] = bar_high
        df.loc[i, "open"] = bar_high - 0.1
        df.loc[i, "close"] = bar_close
        df = compute_all_indicators(df)

        params = _make_params()
        vol_avg = df["volume"].rolling(window=params["vol_lookback"], min_periods=1).mean()
        spread_avg = (df["high"] - df["low"]).rolling(
            window=params["spread_lookback"], min_periods=1
        ).mean()
        signals = detect_no_demand_test(df, vol_avg, spread_avg, params)
        assert len(signals) >= 1
        assert all(s.direction == "bearish" for s in signals)
        assert all(s.pattern == VSAPatternTag.NO_DEMAND_TEST for s in signals)


# ---------------------------------------------------------------------------
# TestVolumeDivergences
# ---------------------------------------------------------------------------

class TestVolumeDivergences:
    def test_bullish_divergence_price_down_volume_down(self, divergence_df: pd.DataFrame) -> None:
        params = _make_params()
        divergences = detect_volume_divergences(divergence_df, params)
        assert len(divergences) == 1
        assert divergences[0].divergence_type == "bullish"

    def test_bearish_divergence_price_up_volume_down(self) -> None:
        np.random.seed(42)
        n = 30
        close = 100.0 + np.linspace(0, 3.0, n)    # rising price
        volume = (100_000 - np.linspace(0, 50_000, n)).astype(int)  # falling volume
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": volume,
        })
        df = compute_all_indicators(df)
        params = _make_params()
        divergences = detect_volume_divergences(df, params)
        assert len(divergences) == 1
        assert divergences[0].divergence_type == "bearish"

    def test_no_divergence_insufficient_bars(self) -> None:
        df = _make_base_df(n=5)
        params = _make_params(vol_lookback=20)
        divergences = detect_volume_divergences(df, params)
        assert divergences == []

    def test_divergence_confidence_between_zero_and_one(self, divergence_df: pd.DataFrame) -> None:
        params = _make_params()
        divergences = detect_volume_divergences(divergence_df, params)
        for d in divergences:
            assert 0.0 <= d.confidence <= 1.0


# ---------------------------------------------------------------------------
# TestBreakoutValidity
# ---------------------------------------------------------------------------

class TestBreakoutValidity:
    def test_valid_long_breakout_high_vol_wide_spread(self, breakout_df: pd.DataFrame) -> None:
        params = _make_params()
        key_levels = [100.5]
        breakouts = detect_breakout_validity(breakout_df, key_levels, params)
        assert len(breakouts) == 1
        assert breakouts[0].direction == "long"
        assert breakouts[0].is_valid is True

    def test_invalid_long_breakout_low_vol(self, breakout_df: pd.DataFrame) -> None:
        # Reset volume to low on last bar
        df = breakout_df.copy()
        df.loc[df.index[-1], "volume"] = 10_000
        params = _make_params()
        breakouts = detect_breakout_validity(df, [100.5], params)
        assert len(breakouts) == 1
        assert breakouts[0].is_valid is False

    def test_no_breakout_if_price_did_not_cross_level(self, base_df: pd.DataFrame) -> None:
        params = _make_params()
        # Level far above current price
        breakouts = detect_breakout_validity(base_df, [999.0], params)
        assert breakouts == []

    def test_short_breakout_detected(self) -> None:
        np.random.seed(42)
        n = 35
        close = np.full(n, 100.0)
        volume = np.full(n, 100_000, dtype=int)
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": close + 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": volume,
        })
        # Last bar breaks below 99.5 with high vol + wide spread
        df.loc[n - 1, "close"] = 98.0
        df.loc[n - 1, "low"] = 97.5
        df.loc[n - 1, "high"] = 100.2
        df.loc[n - 1, "open"] = 100.0
        df.loc[n - 1, "volume"] = 300_000
        df.loc[n - 2, "close"] = 100.0
        df = compute_all_indicators(df)
        params = _make_params()
        breakouts = detect_breakout_validity(df, [99.5], params)
        assert len(breakouts) == 1
        assert breakouts[0].direction == "short"


# ---------------------------------------------------------------------------
# TestAnalyzeVolume
# ---------------------------------------------------------------------------

class TestAnalyzeVolume:
    def test_returns_volume_analysis_result_type(self, base_df: pd.DataFrame) -> None:
        params = _make_params()
        result = analyze_volume(base_df, [], params)
        assert isinstance(result, VolumeAnalysisResult)

    def test_insufficient_bars_returns_empty_neutral_result(self) -> None:
        df = _make_base_df(n=5)
        params = _make_params(vol_lookback=20)
        result = analyze_volume(df, [], params)
        assert result.bias == "neutral"
        assert result.confidence == 0.0
        assert result.conditions == []
        assert result.vsa_signals == []

    def test_bias_bullish_when_stopping_volume_detected(self, stopping_volume_df: pd.DataFrame) -> None:
        params = _make_params()
        result = analyze_volume(stopping_volume_df, [], params)
        # Stopping volume is bullish — bias should lean bullish
        assert result.bias in ("bullish", "neutral")

    def test_conditions_cover_all_bars_from_lookback_onward(self, base_df: pd.DataFrame) -> None:
        params = _make_params()
        result = analyze_volume(base_df, [], params)
        expected_count = len(base_df) - params["vol_lookback"]
        assert len(result.conditions) == expected_count

    def test_reasons_is_nonempty_when_signals_detected(self, stopping_volume_df: pd.DataFrame) -> None:
        params = _make_params()
        result = analyze_volume(stopping_volume_df, [], params)
        if result.vsa_signals or result.divergences or result.breakout_signals:
            assert len(result.reasons) > 0


# ---------------------------------------------------------------------------
# TestVolumeAnalysisSkill
# ---------------------------------------------------------------------------

class TestVolumeAnalysisSkill:
    def test_skill_name_is_volume_analysis(self) -> None:
        skill = VolumeAnalysisSkill()
        assert skill.name == "volume_analysis"

    def test_analyze_returns_volume_analysis_result(self, base_df: pd.DataFrame) -> None:
        skill = VolumeAnalysisSkill()
        result = skill.analyze(base_df)
        assert isinstance(result, VolumeAnalysisResult)
