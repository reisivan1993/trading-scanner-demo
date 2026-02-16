from __future__ import annotations

from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from packages.core.models import SRZone
from packages.skills.base import BaseSkill

DEFAULT_PIVOT_WINDOW = 3
DEFAULT_CLUSTER_ATR_FACTOR = 0.6
DEFAULT_RECENCY_DECAY = 0.95


def find_swing_highs(df: pd.DataFrame, window: int = DEFAULT_PIVOT_WINDOW) -> list[int]:
    """Find swing high indices where high[i] is the max within ±window bars."""
    highs: list[int] = []
    high_vals = df["high"].values
    for i in range(window, len(df) - window):
        local_max = True
        for j in range(i - window, i + window + 1):
            if j != i and high_vals[j] >= high_vals[i]:
                local_max = False
                break
        if local_max:
            highs.append(i)
    return highs


def find_swing_lows(df: pd.DataFrame, window: int = DEFAULT_PIVOT_WINDOW) -> list[int]:
    """Find swing low indices where low[i] is the min within ±window bars."""
    lows: list[int] = []
    low_vals = df["low"].values
    for i in range(window, len(df) - window):
        local_min = True
        for j in range(i - window, i + window + 1):
            if j != i and low_vals[j] <= low_vals[i]:
                local_min = False
                break
        if local_min:
            lows.append(i)
    return lows


def cluster_levels(
    prices: list[float],
    indices: list[int],
    tolerance: float,
    total_bars: int,
) -> list[dict[str, Any]]:
    """Cluster nearby price levels within tolerance. Returns cluster info."""
    if not prices:
        return []

    sorted_pairs = sorted(zip(prices, indices))
    clusters: list[dict[str, Any]] = []
    current_cluster_prices: list[float] = [sorted_pairs[0][0]]
    current_cluster_indices: list[int] = [sorted_pairs[0][1]]

    for price, idx in sorted_pairs[1:]:
        if price - np.mean(current_cluster_prices) <= tolerance:
            current_cluster_prices.append(price)
            current_cluster_indices.append(idx)
        else:
            clusters.append({
                "price": float(np.mean(current_cluster_prices)),
                "touches": len(current_cluster_prices),
                "indices": current_cluster_indices[:],
            })
            current_cluster_prices = [price]
            current_cluster_indices = [idx]

    clusters.append({
        "price": float(np.mean(current_cluster_prices)),
        "touches": len(current_cluster_prices),
        "indices": current_cluster_indices[:],
    })

    return clusters


def compute_zone_strength(
    touches: int,
    indices: list[int],
    total_bars: int,
    volumes: pd.Series | None = None,
) -> float:
    """Compute zone strength based on touches, recency, and volume."""
    touch_score = min(touches / 5.0, 1.0)

    recency_score = 0.0
    if indices and total_bars > 0:
        most_recent = max(indices)
        recency_score = most_recent / total_bars

    volume_score = 0.5
    if volumes is not None and len(indices) > 0:
        valid_indices = [i for i in indices if i < len(volumes)]
        if valid_indices:
            zone_vol = volumes.iloc[valid_indices].mean()
            avg_vol = volumes.mean()
            if avg_vol > 0:
                volume_score = min(zone_vol / avg_vol, 2.0) / 2.0

    return 0.4 * touch_score + 0.35 * recency_score + 0.25 * volume_score


def detect_sr_zones(
    df: pd.DataFrame,
    pivot_window: int = DEFAULT_PIVOT_WINDOW,
    atr_factor: float = DEFAULT_CLUSTER_ATR_FACTOR,
) -> list[SRZone]:
    """Detect support and resistance zones from a DataFrame with indicators.

    Requires 'atr_14' column in the DataFrame (from compute_all_indicators).
    """
    if len(df) < pivot_window * 2 + 1:
        return []

    current_atr = df["atr_14"].iloc[-1] if "atr_14" in df.columns else 1.0
    tolerance = atr_factor * current_atr
    total_bars = len(df)

    swing_high_indices = find_swing_highs(df, pivot_window)
    swing_low_indices = find_swing_lows(df, pivot_window)

    zones: list[SRZone] = []

    # Resistance zones from swing highs
    if swing_high_indices:
        high_prices = [float(df["high"].iloc[i]) for i in swing_high_indices]
        clusters = cluster_levels(high_prices, swing_high_indices, tolerance, total_bars)
        volumes = df["volume"] if "volume" in df.columns else None
        for c in clusters:
            strength = compute_zone_strength(c["touches"], c["indices"], total_bars, volumes)
            zones.append(SRZone(
                price=Decimal(str(round(c["price"], 2))),
                zone_type="resistance",
                touches=c["touches"],
                strength=round(strength, 4),
            ))

    # Support zones from swing lows
    if swing_low_indices:
        low_prices = [float(df["low"].iloc[i]) for i in swing_low_indices]
        clusters = cluster_levels(low_prices, swing_low_indices, tolerance, total_bars)
        volumes = df["volume"] if "volume" in df.columns else None
        for c in clusters:
            strength = compute_zone_strength(c["touches"], c["indices"], total_bars, volumes)
            zones.append(SRZone(
                price=Decimal(str(round(c["price"], 2))),
                zone_type="support",
                touches=c["touches"],
                strength=round(strength, 4),
            ))

    return sorted(zones, key=lambda z: z.strength, reverse=True)


class SupportResistanceSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "support_resistance"

    def analyze(self, df: pd.DataFrame, **kwargs: Any) -> list[SRZone]:
        pivot_window = kwargs.get("pivot_window", DEFAULT_PIVOT_WINDOW)
        atr_factor = kwargs.get("atr_factor", DEFAULT_CLUSTER_ATR_FACTOR)
        return detect_sr_zones(df, pivot_window, atr_factor)
