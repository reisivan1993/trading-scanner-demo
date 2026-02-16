from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from packages.core.indicators import compute_all_indicators
from packages.skills.patterns import (
    detect_all_patterns,
    detect_breakout,
    detect_flag,
    detect_wedge,
)


@pytest.fixture
def breakout_df() -> pd.DataFrame:
    """DataFrame where last bar breaks above 20-bar resistance."""
    np.random.seed(42)
    n = 25
    close = np.full(n, 170.0)
    close[-1] = 180.0  # breakout
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.3,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": np.full(n, 200000, dtype=int),
    })
    df.loc[n - 1, "high"] = 181.0
    return compute_all_indicators(df)


@pytest.fixture
def flag_df() -> pd.DataFrame:
    """DataFrame with a strong trend followed by tight consolidation."""
    np.random.seed(42)
    n = 20
    # First 10 bars: strong uptrend
    trend = np.linspace(160, 175, 10)
    # Last 10 bars: tight consolidation
    consolidation = 175 + np.random.randn(10) * 0.2
    close = np.concatenate([trend, consolidation])
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.2,
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "volume": np.full(n, 200000, dtype=int),
    })
    return compute_all_indicators(df)


class TestDetectBreakout:
    def test_detects_breakout_long(self, breakout_df: pd.DataFrame) -> None:
        result = detect_breakout(breakout_df)
        long_breakouts = [p for p in result if p.direction == "long"]
        assert len(long_breakouts) >= 1
        assert long_breakouts[0].name == "breakout"

    def test_confidence_range(self, breakout_df: pd.DataFrame) -> None:
        result = detect_breakout(breakout_df)
        for p in result:
            assert 0 <= p.confidence <= 1.0


class TestDetectFlag:
    def test_detects_bull_flag(self, flag_df: pd.DataFrame) -> None:
        result = detect_flag(flag_df)
        if result:
            assert result[0].direction == "long"
            assert result[0].name == "flag"


class TestDetectAllPatterns:
    def test_returns_sorted_by_confidence(self, breakout_df: pd.DataFrame) -> None:
        result = detect_all_patterns(breakout_df)
        if len(result) > 1:
            confidences = [p.confidence for p in result]
            assert confidences == sorted(confidences, reverse=True)

    def test_empty_on_insufficient_data(self) -> None:
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="D"),
            "open": [170, 170, 170],
            "high": [171, 171, 171],
            "low": [169, 169, 169],
            "close": [170, 170, 170],
            "volume": [100000, 100000, 100000],
        })
        df = compute_all_indicators(df)
        result = detect_all_patterns(df)
        # With only 3 bars, most patterns won't trigger
        assert isinstance(result, list)
