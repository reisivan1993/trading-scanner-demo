from __future__ import annotations

from typing import Any

import pandas as pd

from packages.core.models import (
    PatternMatch,
    ScoringBreakdown,
    SRZone,
    VectorCandle,
)
from packages.skills.base import BaseSkill

# Default scoring weights
WEIGHTS = {
    "confluence": 0.22,
    "invalidation": 0.18,
    "rr": 0.18,
    "momentum": 0.14,
    "volume": 0.12,
    "pattern": 0.10,
    "cleanliness": 0.06,
}


def score_confluence(
    sr_zones: list[SRZone],
    vector_candles: list[VectorCandle],
    patterns: list[PatternMatch],
) -> float:
    """Score confluence: how many independent signals align (0-100)."""
    signals = 0
    if sr_zones:
        signals += min(len(sr_zones), 3)
    if vector_candles:
        signals += min(len(vector_candles), 2)
    if patterns:
        signals += min(len(patterns), 2)
    return min(signals / 7.0 * 100, 100.0)


def score_invalidation(rr_ratio: float, stop_distance_atr: float | None = None) -> float:
    """Score invalidation clarity: clear stop + good RR = high score (0-100)."""
    rr_score = min(rr_ratio / 5.0 * 100, 100.0)
    if stop_distance_atr is not None:
        # Prefer stops between 0.5 and 2.0 ATR
        if 0.5 <= stop_distance_atr <= 2.0:
            stop_score = 100.0
        elif stop_distance_atr < 0.5:
            stop_score = stop_distance_atr / 0.5 * 100
        else:
            stop_score = max(0, 100 - (stop_distance_atr - 2.0) * 25)
        return (rr_score + stop_score) / 2.0
    return rr_score


def score_rr(rr_ratio: float) -> float:
    """Score reward-to-risk ratio (0-100)."""
    return min(rr_ratio / 5.0 * 100, 100.0)


def score_momentum(rsi: float | None = None, ema_alignment: bool = False) -> float:
    """Score momentum: RSI trend strength + EMA alignment (0-100)."""
    score = 50.0  # neutral baseline

    if rsi is not None:
        if 50 < rsi < 70:
            score += 25  # bullish momentum
        elif 30 < rsi < 50:
            score -= 10  # weakening
        elif rsi >= 70:
            score += 15  # strong but overbought risk
        elif rsi <= 30:
            score -= 15  # oversold

    if ema_alignment:
        score += 25

    return min(max(score, 0), 100.0)


def score_volume(rvol: float | None = None) -> float:
    """Score relative volume (0-100)."""
    if rvol is None:
        return 50.0
    if rvol >= 2.0:
        return 100.0
    if rvol >= 1.5:
        return 80.0
    if rvol >= 1.0:
        return 60.0
    return max(rvol / 1.0 * 40, 0)


def score_pattern(patterns: list[PatternMatch]) -> float:
    """Score pattern quality (0-100)."""
    if not patterns:
        return 0.0
    best = max(p.confidence for p in patterns)
    return best * 100.0


def score_cleanliness(df: pd.DataFrame) -> float:
    """Score chart cleanliness: low noise = higher score (0-100).

    Measures average body-to-range ratio over recent bars.
    """
    if len(df) < 5:
        return 50.0

    recent = df.iloc[-10:]
    body = (recent["close"] - recent["open"]).abs()
    total_range = recent["high"] - recent["low"]
    valid = total_range > 0
    if valid.sum() == 0:
        return 50.0

    avg_body_ratio = (body[valid] / total_range[valid]).mean()
    return min(avg_body_ratio * 100, 100.0)


def compute_score(
    *,
    sr_zones: list[SRZone] | None = None,
    vector_candles: list[VectorCandle] | None = None,
    patterns: list[PatternMatch] | None = None,
    rr_ratio: float = 0.0,
    stop_distance_atr: float | None = None,
    rsi_val: float | None = None,
    ema_alignment: bool = False,
    rvol_val: float | None = None,
    df: pd.DataFrame | None = None,
    web_intel_modifier: float = 0.0,
) -> ScoringBreakdown:
    """Compute the full scoring breakdown."""
    _sr = sr_zones or []
    _vc = vector_candles or []
    _pat = patterns or []

    confluence = score_confluence(_sr, _vc, _pat)
    invalidation = score_invalidation(rr_ratio, stop_distance_atr)
    rr = score_rr(rr_ratio)
    momentum = score_momentum(rsi_val, ema_alignment)
    volume = score_volume(rvol_val)
    pattern = score_pattern(_pat)
    cleanliness = score_cleanliness(df) if df is not None else 50.0

    raw_total = (
        confluence * WEIGHTS["confluence"]
        + invalidation * WEIGHTS["invalidation"]
        + rr * WEIGHTS["rr"]
        + momentum * WEIGHTS["momentum"]
        + volume * WEIGHTS["volume"]
        + pattern * WEIGHTS["pattern"]
        + cleanliness * WEIGHTS["cleanliness"]
    )

    total = max(0.0, min(100.0, raw_total + web_intel_modifier * 100))

    return ScoringBreakdown(
        confluence=round(confluence, 2),
        invalidation=round(invalidation, 2),
        rr=round(rr, 2),
        momentum=round(momentum, 2),
        volume=round(volume, 2),
        pattern=round(pattern, 2),
        cleanliness=round(cleanliness, 2),
        web_intel_modifier=round(web_intel_modifier, 4),
        total=round(total, 2),
    )


class ScoringSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "scoring"

    def analyze(self, df: pd.DataFrame, **kwargs: Any) -> ScoringBreakdown:
        return compute_score(df=df, **kwargs)
