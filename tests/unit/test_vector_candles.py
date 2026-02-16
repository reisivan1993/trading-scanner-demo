from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from packages.core.indicators import compute_all_indicators
from packages.core.models import Timeframe
from packages.skills.vector_candles import detect_vector_candles


@pytest.fixture
def df_with_vector_candle() -> pd.DataFrame:
    """DataFrame where the last bar is a vector candle (large TR + high volume)."""
    np.random.seed(42)
    n = 30
    close = 170.0 + np.cumsum(np.random.randn(n) * 0.3)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.2,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": np.full(n, 200000, dtype=int),
    })
    # Make last bar a vector candle: huge range and huge volume
    df.loc[n - 1, "high"] = df.loc[n - 1, "close"] + 5.0
    df.loc[n - 1, "low"] = df.loc[n - 1, "close"] - 5.0
    df.loc[n - 1, "volume"] = 2000000
    return compute_all_indicators(df)


@pytest.fixture
def quiet_df() -> pd.DataFrame:
    """DataFrame with no vector candles (small ranges, normal volume)."""
    np.random.seed(42)
    n = 30
    close = np.full(n, 170.0)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close - 0.05,
        "high": close + 0.1,
        "low": close - 0.1,
        "close": close,
        "volume": np.full(n, 200000, dtype=int),
    })
    return compute_all_indicators(df)


class TestDetectVectorCandles:
    def test_detects_large_bar(self, df_with_vector_candle: pd.DataFrame) -> None:
        result = detect_vector_candles(df_with_vector_candle)
        assert len(result) >= 1

    def test_vector_candle_has_valid_tag(self, df_with_vector_candle: pd.DataFrame) -> None:
        result = detect_vector_candles(df_with_vector_candle)
        for vc in result:
            assert vc.tag in ("follow-through", "absorption", "rejection")

    def test_atr_multiple_above_threshold(self, df_with_vector_candle: pd.DataFrame) -> None:
        result = detect_vector_candles(df_with_vector_candle, atr_threshold=1.8)
        for vc in result:
            assert vc.atr_multiple >= 1.8

    def test_volume_multiple_above_threshold(self, df_with_vector_candle: pd.DataFrame) -> None:
        result = detect_vector_candles(df_with_vector_candle, volume_threshold=2.0)
        for vc in result:
            assert vc.volume_multiple >= 2.0

    def test_quiet_market_no_vectors(self, quiet_df: pd.DataFrame) -> None:
        result = detect_vector_candles(quiet_df)
        assert len(result) == 0

    def test_empty_df(self) -> None:
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "atr_14"])
        assert detect_vector_candles(df) == []
