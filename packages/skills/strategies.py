from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

import pandas as pd

from packages.core.models import (
    PatternMatch,
    ScoringBreakdown,
    SRZone,
    VectorCandle,
)
from packages.skills.patterns import detect_doji, detect_structure_break
from packages.skills.scoring import (
    score_cleanliness,
    score_momentum,
    score_pattern,
    score_rr,
    score_volume,
)

StrategyName = Literal["swing", "position"]


@dataclass(frozen=True)
class ScanStrategy:
    """Defines a scan mode's screening filter and scoring weights."""

    name: StrategyName
    display_name: str
    description: str
    result_limit: int = 20
    screen: Callable[..., bool] = field(repr=False)
    score_fn: Callable[..., ScoringBreakdown] = field(repr=False)
    extra_patterns: Callable[..., list[PatternMatch]] = field(
        repr=False, default=lambda df: [],
    )


# ---------------------------------------------------------------------------
# Screening functions
# ---------------------------------------------------------------------------

def screen_swing(
    df: pd.DataFrame,
    sr_zones: list[SRZone],
    vector_candles: list[VectorCandle],
    patterns: list[PatternMatch],
) -> bool:
    """Extended from SMA20 + doji + recent directional volume bars."""
    if len(df) < 25 or "sma_20" not in df.columns:
        return False

    last_close = float(df["close"].iloc[-1])
    sma_20_val = float(df["sma_20"].iloc[-1])
    atr_val = float(df["atr_14"].iloc[-1]) if "atr_14" in df.columns else 0.0

    if atr_val == 0:
        return False

    distance_from_sma20 = abs(last_close - sma_20_val)
    if distance_from_sma20 < 1.5 * atr_val:
        return False

    doji_patterns = detect_doji(df, threshold=0.15, lookback=5)
    if not doji_patterns:
        return False

    recent = df.iloc[-5:]
    avg_volume = float(df["volume"].iloc[-25:].mean())
    directional_bars = 0
    for _, row in recent.iterrows():
        total_range = float(row["high"] - row["low"])
        if total_range == 0:
            continue
        body = abs(float(row["close"] - row["open"]))
        if body / total_range > 0.5 and float(row["volume"]) > avg_volume:
            directional_bars += 1

    return directional_bars >= 2


def screen_position(
    df: pd.DataFrame,
    sr_zones: list[SRZone],
    vector_candles: list[VectorCandle],
    patterns: list[PatternMatch],
) -> bool:
    """Near SMA150 + structure break + volume + institutional signal."""
    if len(df) < 150 or "sma_150" not in df.columns:
        return False

    last_close = float(df["close"].iloc[-1])
    sma_150_val = float(df["sma_150"].iloc[-1])

    if sma_150_val == 0:
        return False

    distance_pct = abs(last_close - sma_150_val) / sma_150_val * 100
    if distance_pct > 3.0:
        return False

    structure_patterns = detect_structure_break(df, lookback=20)
    if not structure_patterns:
        return False

    rvol_val = float(df["rvol_20"].iloc[-1]) if "rvol_20" in df.columns else 0.0
    if rvol_val < 1.0:
        return False

    support_zones = [z for z in sr_zones if z.zone_type == "support"]
    return len(vector_candles) > 0 or len(support_zones) > 0


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

_SWING_WEIGHTS = {
    "ma_distance": 0.25,
    "reversal_signal": 0.20,
    "volume": 0.18,
    "momentum": 0.15,
    "pattern": 0.10,
    "cleanliness": 0.06,
    "rr": 0.06,
}

_POSITION_WEIGHTS = {
    "ma_proximity": 0.22,
    "structure": 0.22,
    "volume": 0.18,
    "institutional": 0.15,
    "momentum": 0.10,
    "pattern": 0.07,
    "rr": 0.06,
}


def score_swing(
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
    """Score for swing mode: mean-reversion-oriented."""
    _pat = patterns or []

    ma_distance_score = 50.0
    if df is not None and "sma_20" in df.columns and "atr_14" in df.columns:
        last_close = float(df["close"].iloc[-1])
        sma_20_val = float(df["sma_20"].iloc[-1])
        atr_val = float(df["atr_14"].iloc[-1])
        if atr_val > 0:
            distance_atr = abs(last_close - sma_20_val) / atr_val
            ma_distance_score = min(distance_atr / 4.0 * 100, 100.0)

    doji_patterns = [p for p in _pat if p.name == "doji"]
    reversal_score = 0.0
    if doji_patterns:
        reversal_score = max(p.confidence for p in doji_patterns) * 100.0

    volume_score = score_volume(rvol_val)
    momentum_score = score_momentum(rsi_val, ema_alignment)
    pattern_score = score_pattern([p for p in _pat if p.name != "doji"])
    cleanliness_val = score_cleanliness(df) if df is not None else 50.0
    rr_score = score_rr(rr_ratio)

    w = _SWING_WEIGHTS
    raw = (
        ma_distance_score * w["ma_distance"]
        + reversal_score * w["reversal_signal"]
        + volume_score * w["volume"]
        + momentum_score * w["momentum"]
        + pattern_score * w["pattern"]
        + cleanliness_val * w["cleanliness"]
        + rr_score * w["rr"]
    )
    total = max(0.0, min(100.0, raw + web_intel_modifier * 100))

    return ScoringBreakdown(
        confluence=round(ma_distance_score, 2),
        invalidation=round(reversal_score, 2),
        rr=round(rr_score, 2),
        momentum=round(momentum_score, 2),
        volume=round(volume_score, 2),
        pattern=round(pattern_score, 2),
        cleanliness=round(cleanliness_val, 2),
        web_intel_modifier=round(web_intel_modifier, 4),
        total=round(total, 2),
    )


def score_position(
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
    """Score for position entry mode: trend-following at institutional levels."""
    _sr = sr_zones or []
    _vc = vector_candles or []
    _pat = patterns or []

    ma_proximity_score = 50.0
    if df is not None and "sma_150" in df.columns:
        last_close = float(df["close"].iloc[-1])
        sma_150_val = float(df["sma_150"].iloc[-1])
        if sma_150_val > 0:
            distance_pct = abs(last_close - sma_150_val) / sma_150_val * 100
            ma_proximity_score = max(0.0, 100.0 - distance_pct * 33.0)

    structure_patterns = [p for p in _pat if p.name == "structure_break"]
    structure_score = 0.0
    if structure_patterns:
        structure_score = max(p.confidence for p in structure_patterns) * 100.0

    volume_score = score_volume(rvol_val)

    institutional_score = 0.0
    support_zones = [z for z in _sr if z.zone_type == "support"]
    if _vc:
        institutional_score += 50.0
    if support_zones:
        institutional_score += support_zones[0].strength * 50.0
    institutional_score = min(institutional_score, 100.0)

    momentum_score = score_momentum(rsi_val, ema_alignment)
    pattern_score = score_pattern([p for p in _pat if p.name != "structure_break"])
    rr_score = score_rr(rr_ratio)

    w = _POSITION_WEIGHTS
    raw = (
        ma_proximity_score * w["ma_proximity"]
        + structure_score * w["structure"]
        + volume_score * w["volume"]
        + institutional_score * w["institutional"]
        + momentum_score * w["momentum"]
        + pattern_score * w["pattern"]
        + rr_score * w["rr"]
    )
    total = max(0.0, min(100.0, raw + web_intel_modifier * 100))

    return ScoringBreakdown(
        confluence=round(ma_proximity_score, 2),
        invalidation=round(structure_score, 2),
        rr=round(rr_score, 2),
        momentum=round(momentum_score, 2),
        volume=round(volume_score, 2),
        pattern=round(pattern_score, 2),
        cleanliness=round(institutional_score, 2),
        web_intel_modifier=round(web_intel_modifier, 4),
        total=round(total, 2),
    )


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

def _swing_extra_patterns(df: pd.DataFrame) -> list[PatternMatch]:
    return detect_doji(df, threshold=0.15, lookback=5)


def _position_extra_patterns(df: pd.DataFrame) -> list[PatternMatch]:
    return detect_structure_break(df, lookback=20)


STRATEGIES: dict[str, ScanStrategy] = {
    "swing": ScanStrategy(
        name="swing",
        display_name="Short-Term Swing",
        description="Mean reversion: extended from MA20 + doji + directional volume",
        result_limit=20,
        screen=screen_swing,
        score_fn=score_swing,
        extra_patterns=_swing_extra_patterns,
    ),
    "position": ScanStrategy(
        name="position",
        display_name="Long Position Entry",
        description="Trend following: near SMA150 + structure break + volume",
        result_limit=20,
        screen=screen_position,
        score_fn=score_position,
        extra_patterns=_position_extra_patterns,
    ),
}


def get_strategy(name: str) -> ScanStrategy:
    """Get a strategy by name. Raises ValueError if not found."""
    if name not in STRATEGIES:
        raise ValueError(
            f"Unknown strategy: {name}. Available: {list(STRATEGIES.keys())}"
        )
    return STRATEGIES[name]
