from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pandas as pd

from packages.core.models import OHLCVBar, Timeframe

# US market session times (Eastern)
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
MINUTES_PER_65M_BAR = 65
BARS_PER_SESSION_65M = 6  # 09:30, 10:35, 11:40, 12:45, 13:50, 14:55


def bars_to_dataframe(bars: list[OHLCVBar]) -> pd.DataFrame:
    """Convert a list of OHLCVBar to a pandas DataFrame."""
    if not bars:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    records = [
        {
            "timestamp": b.timestamp,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": b.volume,
        }
        for b in bars
    ]
    df = pd.DataFrame(records)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def dataframe_to_bars(df: pd.DataFrame, timeframe: Timeframe) -> list[OHLCVBar]:
    """Convert a pandas DataFrame back to a list of OHLCVBar."""
    bars: list[OHLCVBar] = []
    for _, row in df.iterrows():
        bars.append(
            OHLCVBar(
                timestamp=row["timestamp"],
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=int(row["volume"]),
                timeframe=timeframe,
            )
        )
    return bars


def _aggregate_group(group: pd.DataFrame) -> dict:
    """Aggregate OHLCV for a group of bars."""
    return {
        "timestamp": group["timestamp"].iloc[0],
        "open": group["open"].iloc[0],
        "high": group["high"].max(),
        "low": group["low"].min(),
        "close": group["close"].iloc[-1],
        "volume": group["volume"].sum(),
    }


def resample_1m_to_15m(bars_1m: list[OHLCVBar]) -> list[OHLCVBar]:
    """Resample 1-minute bars to 15-minute bars."""
    df = bars_to_dataframe(bars_1m)
    if df.empty:
        return []

    df["ts"] = pd.to_datetime(df["timestamp"])
    df["group"] = df["ts"].dt.floor("15min")

    result_rows = []
    for _, group in df.groupby("group"):
        result_rows.append(_aggregate_group(group))

    result_df = pd.DataFrame(result_rows).sort_values("timestamp").reset_index(drop=True)
    return dataframe_to_bars(result_df, Timeframe.M15)


def _compute_65m_bar_index(ts: datetime) -> int:
    """Compute the 65-minute bar index for an intraday timestamp.

    Bar boundaries: 09:30 (0), 10:35 (1), 11:40 (2), 12:45 (3), 13:50 (4), 14:55 (5).
    """
    market_open_dt = ts.replace(hour=9, minute=30, second=0, microsecond=0)
    minutes_since_open = (ts - market_open_dt).total_seconds() / 60.0
    if minutes_since_open < 0:
        return 0
    idx = int(minutes_since_open // MINUTES_PER_65M_BAR)
    return min(idx, BARS_PER_SESSION_65M - 1)


def resample_1m_to_65m(bars_1m: list[OHLCVBar]) -> list[OHLCVBar]:
    """Resample 1-minute bars to 65-minute bars (6 bars per session).

    Bar boundaries aligned to 09:30 ET:
    - Bar 0: 09:30-10:34
    - Bar 1: 10:35-11:39
    - Bar 2: 11:40-12:44
    - Bar 3: 12:45-13:49
    - Bar 4: 13:50-14:54
    - Bar 5: 14:55-16:00
    """
    df = bars_to_dataframe(bars_1m)
    if df.empty:
        return []

    df["ts"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["ts"].dt.date
    df["bar_idx"] = df["ts"].apply(lambda t: _compute_65m_bar_index(t))
    df["group_key"] = df["date"].astype(str) + "_" + df["bar_idx"].astype(str)

    result_rows = []
    for _, group in df.groupby("group_key", sort=False):
        result_rows.append(_aggregate_group(group))

    result_df = pd.DataFrame(result_rows).sort_values("timestamp").reset_index(drop=True)
    return dataframe_to_bars(result_df, Timeframe.M65)


def resample_1d_to_1w(bars_1d: list[OHLCVBar]) -> list[OHLCVBar]:
    """Resample daily bars to weekly bars (Monday-aligned)."""
    df = bars_to_dataframe(bars_1d)
    if df.empty:
        return []

    df["ts"] = pd.to_datetime(df["timestamp"])
    df["week"] = df["ts"].dt.isocalendar().week.astype(int)
    df["year"] = df["ts"].dt.isocalendar().year.astype(int)
    df["group_key"] = df["year"].astype(str) + "_" + df["week"].astype(str)

    result_rows = []
    for _, group in df.groupby("group_key", sort=False):
        result_rows.append(_aggregate_group(group))

    result_df = pd.DataFrame(result_rows).sort_values("timestamp").reset_index(drop=True)
    return dataframe_to_bars(result_df, Timeframe.W1)
