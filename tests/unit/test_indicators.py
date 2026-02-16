from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from packages.core.indicators import atr, compute_all_indicators, ema, rsi, rvol, sma, vwap


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """30 rows of synthetic OHLCV data."""
    np.random.seed(42)
    n = 30
    close = 170.0 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame(
        {
            "open": close - np.random.rand(n) * 0.3,
            "high": close + np.random.rand(n) * 1.0,
            "low": close - np.random.rand(n) * 1.0,
            "close": close,
            "volume": np.random.randint(100000, 500000, n),
        }
    )


class TestATR:
    def test_atr_length(self, sample_df: pd.DataFrame) -> None:
        result = atr(sample_df, 14)
        assert len(result) == len(sample_df)

    def test_atr_positive(self, sample_df: pd.DataFrame) -> None:
        result = atr(sample_df, 14)
        assert (result > 0).all()


class TestEMA:
    def test_ema_length(self, sample_df: pd.DataFrame) -> None:
        result = ema(sample_df, 9)
        assert len(result) == len(sample_df)

    def test_ema_tracks_close(self, sample_df: pd.DataFrame) -> None:
        result = ema(sample_df, 1)
        pd.testing.assert_series_equal(result, sample_df["close"], check_names=False)


class TestSMA:
    def test_sma_length(self, sample_df: pd.DataFrame) -> None:
        result = sma(sample_df, 20)
        assert len(result) == len(sample_df)


class TestRSI:
    def test_rsi_range(self, sample_df: pd.DataFrame) -> None:
        result = rsi(sample_df, 14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_length(self, sample_df: pd.DataFrame) -> None:
        result = rsi(sample_df, 14)
        assert len(result) == len(sample_df)


class TestVWAP:
    def test_vwap_length(self, sample_df: pd.DataFrame) -> None:
        result = vwap(sample_df)
        assert len(result) == len(sample_df)

    def test_vwap_within_price_range(self, sample_df: pd.DataFrame) -> None:
        result = vwap(sample_df)
        assert result.iloc[-1] >= sample_df["low"].min()
        assert result.iloc[-1] <= sample_df["high"].max()


class TestRVOL:
    def test_rvol_first_bar_is_one(self, sample_df: pd.DataFrame) -> None:
        result = rvol(sample_df, 20)
        assert abs(result.iloc[0] - 1.0) < 0.01


class TestComputeAll:
    def test_adds_all_columns(self, sample_df: pd.DataFrame) -> None:
        result = compute_all_indicators(sample_df)
        expected_cols = [
            "atr_14", "ema_9", "ema_20", "ema_50", "ema_200",
            "sma_200", "rsi_14", "vwap", "rvol_20",
        ]
        for col in expected_cols:
            assert col in result.columns

    def test_does_not_modify_original(self, sample_df: pd.DataFrame) -> None:
        original_cols = list(sample_df.columns)
        compute_all_indicators(sample_df)
        assert list(sample_df.columns) == original_cols
