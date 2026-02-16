from __future__ import annotations

import numpy as np
import pandas as pd

from packages.core.resampling import bars_to_dataframe


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    return tr.rolling(window=period, min_periods=1).mean()


def ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Exponential Moving Average."""
    return df[column].ewm(span=period, adjust=False, min_periods=1).mean()


def sma(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Simple Moving Average."""
    return df[column].rolling(window=period, min_periods=1).mean()


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def vwap(df: pd.DataFrame) -> pd.Series:
    """Session VWAP (Volume-Weighted Average Price).

    Assumes all rows belong to the same session. For multi-session data,
    group by date first and apply per session.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    return cum_tp_vol / cum_vol.replace(0, np.nan)


def rvol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Relative Volume: current volume / SMA of volume over `period` bars."""
    avg_vol = df["volume"].rolling(window=period, min_periods=1).mean()
    return df["volume"] / avg_vol.replace(0, np.nan)


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Commodity Channel Index."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    tp_sma = typical_price.rolling(window=period, min_periods=1).mean()
    mean_dev = typical_price.rolling(window=period, min_periods=1).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True,
    )
    return (typical_price - tp_sma) / (0.015 * mean_dev.replace(0, np.nan))


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all standard indicators and add them as columns.

    Expects a DataFrame with columns: open, high, low, close, volume.
    Returns the same DataFrame with indicator columns added.
    """
    result = df.copy()

    result["atr_14"] = atr(result, 14)
    result["ema_9"] = ema(result, 9)
    result["ema_20"] = ema(result, 20)
    result["ema_50"] = ema(result, 50)
    result["ema_200"] = ema(result, 200)
    result["sma_20"] = sma(result, 20)
    result["sma_150"] = sma(result, 150)
    result["sma_200"] = sma(result, 200)
    result["rsi_14"] = rsi(result, 14)
    result["vwap"] = vwap(result)
    result["rvol_20"] = rvol(result, 20)
    result["cci_20"] = cci(result, 20)

    return result
