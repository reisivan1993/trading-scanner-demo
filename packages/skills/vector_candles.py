from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

import numpy as np
import pandas as pd

from packages.core.models import OHLCVBar, Timeframe, VectorCandle
from packages.skills.base import BaseSkill

DEFAULT_ATR_THRESHOLD = 1.8
DEFAULT_VOLUME_THRESHOLD = 2.0
DEFAULT_VOLUME_LOOKBACK = 20


def _classify_vector_candle(
    row: pd.Series,
    prev_close: float | None,
) -> Literal["follow-through", "absorption", "rejection"]:
    """Classify a vector candle based on its structure.

    - follow-through: large body in direction of move, small wicks
    - absorption: large candle that reverses prior direction (engulfing behavior)
    - rejection: large wicks relative to body (indecision / reversal signal)
    """
    body = abs(row["close"] - row["open"])
    total_range = row["high"] - row["low"]

    if total_range == 0:
        return "rejection"

    body_ratio = body / total_range
    upper_wick = row["high"] - max(row["open"], row["close"])
    lower_wick = min(row["open"], row["close"]) - row["low"]
    wick_sum = upper_wick + lower_wick

    # Rejection: wicks dominate (body < 30% of range)
    if body_ratio < 0.30:
        return "rejection"

    # Absorption: direction reversed from prior bar
    if prev_close is not None:
        prior_direction = row["open"] - prev_close
        candle_direction = row["close"] - row["open"]
        if prior_direction != 0 and candle_direction != 0:
            if (prior_direction > 0 and candle_direction < 0) or (
                prior_direction < 0 and candle_direction > 0
            ):
                return "absorption"

    # Follow-through: strong body (body > 60% of range)
    return "follow-through"


def detect_vector_candles(
    df: pd.DataFrame,
    atr_threshold: float = DEFAULT_ATR_THRESHOLD,
    volume_threshold: float = DEFAULT_VOLUME_THRESHOLD,
    volume_lookback: int = DEFAULT_VOLUME_LOOKBACK,
    timeframe: Timeframe = Timeframe.D1,
) -> list[VectorCandle]:
    """Detect vector candles: bars with TR >= atr_threshold*ATR AND vol >= volume_threshold*median(vol).

    Requires 'atr_14' column in the DataFrame.
    """
    if len(df) < volume_lookback or "atr_14" not in df.columns:
        return []

    result: list[VectorCandle] = []
    high = df["high"].values
    low = df["low"].values
    close_vals = df["close"].values
    open_vals = df["open"].values
    atr_vals = df["atr_14"].values
    vol_vals = df["volume"].values

    for i in range(volume_lookback, len(df)):
        tr = high[i] - low[i]
        if atr_vals[i] == 0:
            continue

        atr_multiple = tr / atr_vals[i]
        if atr_multiple < atr_threshold:
            continue

        median_vol = float(np.median(vol_vals[max(0, i - volume_lookback) : i]))
        if median_vol == 0:
            continue

        vol_multiple = vol_vals[i] / median_vol
        if vol_multiple < volume_threshold:
            continue

        row = df.iloc[i]
        prev_close = float(close_vals[i - 1]) if i > 0 else None
        tag = _classify_vector_candle(row, prev_close)

        bar = OHLCVBar(
            timestamp=df["timestamp"].iloc[i] if "timestamp" in df.columns else row.name,
            open=Decimal(str(round(float(open_vals[i]), 2))),
            high=Decimal(str(round(float(high[i]), 2))),
            low=Decimal(str(round(float(low[i]), 2))),
            close=Decimal(str(round(float(close_vals[i]), 2))),
            volume=int(vol_vals[i]),
            timeframe=timeframe,
        )

        result.append(VectorCandle(
            bar=bar,
            tag=tag,
            atr_multiple=round(atr_multiple, 2),
            volume_multiple=round(vol_multiple, 2),
        ))

    return result


class VectorCandleSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "vector_candles"

    def analyze(self, df: pd.DataFrame, **kwargs: Any) -> list[VectorCandle]:
        return detect_vector_candles(
            df,
            atr_threshold=kwargs.get("atr_threshold", DEFAULT_ATR_THRESHOLD),
            volume_threshold=kwargs.get("volume_threshold", DEFAULT_VOLUME_THRESHOLD),
            volume_lookback=kwargs.get("volume_lookback", DEFAULT_VOLUME_LOOKBACK),
            timeframe=kwargs.get("timeframe", Timeframe.D1),
        )
