from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from packages.core.indicators import compute_all_indicators
from packages.skills.support_resistance import (
    cluster_levels,
    compute_zone_strength,
    detect_sr_zones,
    find_swing_highs,
    find_swing_lows,
)


@pytest.fixture
def trending_df() -> pd.DataFrame:
    """DataFrame with clear swing highs and lows."""
    np.random.seed(42)
    n = 60
    # Create a series with clear swings
    t = np.linspace(0, 4 * np.pi, n)
    base = 170.0 + 5.0 * np.sin(t)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": base - 0.2,
        "high": base + 1.5,
        "low": base - 1.5,
        "close": base + 0.2,
        "volume": np.random.randint(100000, 500000, n),
    })
    return compute_all_indicators(df)


class TestSwingDetection:
    def test_find_swing_highs_count(self, trending_df: pd.DataFrame) -> None:
        highs = find_swing_highs(trending_df, window=3)
        assert len(highs) > 0

    def test_find_swing_lows_count(self, trending_df: pd.DataFrame) -> None:
        lows = find_swing_lows(trending_df, window=3)
        assert len(lows) > 0

    def test_swing_highs_are_local_maxima(self, trending_df: pd.DataFrame) -> None:
        highs = find_swing_highs(trending_df, window=3)
        high_vals = trending_df["high"].values
        for i in highs:
            for j in range(max(0, i - 3), min(len(trending_df), i + 4)):
                if j != i:
                    assert high_vals[j] < high_vals[i]


class TestClustering:
    def test_cluster_nearby_levels(self) -> None:
        prices = [170.0, 170.2, 170.1, 175.0, 175.1]
        indices = [0, 5, 10, 20, 25]
        clusters = cluster_levels(prices, indices, tolerance=0.5, total_bars=30)
        assert len(clusters) == 2
        assert clusters[0]["touches"] == 3
        assert clusters[1]["touches"] == 2

    def test_cluster_empty_input(self) -> None:
        assert cluster_levels([], [], 1.0, 30) == []


class TestZoneStrength:
    def test_more_touches_higher_strength(self) -> None:
        s1 = compute_zone_strength(1, [10], 30)
        s2 = compute_zone_strength(5, [10], 30)
        assert s2 > s1

    def test_more_recent_higher_strength(self) -> None:
        s1 = compute_zone_strength(2, [5], 30)
        s2 = compute_zone_strength(2, [25], 30)
        assert s2 > s1


class TestDetectSRZones:
    def test_detects_zones(self, trending_df: pd.DataFrame) -> None:
        zones = detect_sr_zones(trending_df)
        assert len(zones) > 0

    def test_zones_have_correct_types(self, trending_df: pd.DataFrame) -> None:
        zones = detect_sr_zones(trending_df)
        types = {z.zone_type for z in zones}
        assert "support" in types or "resistance" in types

    def test_zones_sorted_by_strength(self, trending_df: pd.DataFrame) -> None:
        zones = detect_sr_zones(trending_df)
        strengths = [z.strength for z in zones]
        assert strengths == sorted(strengths, reverse=True)

    def test_too_few_bars_returns_empty(self) -> None:
        df = pd.DataFrame({
            "high": [170.0, 171.0],
            "low": [169.0, 169.5],
            "close": [170.5, 170.8],
            "volume": [100000, 100000],
            "atr_14": [1.0, 1.0],
        })
        assert detect_sr_zones(df) == []
