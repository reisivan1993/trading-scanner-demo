from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from packages.core.models import PatternMatch
from packages.skills.base import BaseSkill


def detect_breakout(df: pd.DataFrame, lookback: int = 20) -> list[PatternMatch]:
    """Detect breakout above resistance or breakdown below support."""
    if len(df) < lookback + 1:
        return []

    patterns: list[PatternMatch] = []
    recent = df.iloc[-lookback - 1 : -1]
    last = df.iloc[-1]
    resistance = recent["high"].max()
    support = recent["low"].min()
    atr = df["atr_14"].iloc[-1] if "atr_14" in df.columns else 1.0

    # Breakout above resistance
    if last["close"] > resistance:
        excess = (last["close"] - resistance) / atr if atr > 0 else 0
        confidence = min(0.5 + excess * 0.2, 1.0)
        patterns.append(PatternMatch(
            name="breakout",
            direction="long",
            confidence=round(confidence, 2),
            description=f"Close {last['close']:.2f} above {lookback}-bar resistance {resistance:.2f}",
        ))

    # Breakdown below support
    if last["close"] < support:
        excess = (support - last["close"]) / atr if atr > 0 else 0
        confidence = min(0.5 + excess * 0.2, 1.0)
        patterns.append(PatternMatch(
            name="breakdown",
            direction="short",
            confidence=round(confidence, 2),
            description=f"Close {last['close']:.2f} below {lookback}-bar support {support:.2f}",
        ))

    return patterns


def detect_flag(df: pd.DataFrame, trend_len: int = 10, flag_len: int = 5) -> list[PatternMatch]:
    """Detect bull/bear flags (strong move followed by tight consolidation)."""
    if len(df) < trend_len + flag_len + 1:
        return []

    patterns: list[PatternMatch] = []
    trend_section = df.iloc[-(trend_len + flag_len) : -flag_len]
    flag_section = df.iloc[-flag_len:]
    atr = df["atr_14"].iloc[-1] if "atr_14" in df.columns else 1.0

    trend_move = trend_section["close"].iloc[-1] - trend_section["close"].iloc[0]
    flag_range = flag_section["high"].max() - flag_section["low"].min()

    if atr == 0:
        return patterns

    trend_atr_multiple = abs(trend_move) / atr
    flag_atr_multiple = flag_range / atr

    # Flag: strong trend (>2 ATR) followed by tight consolidation (<1.5 ATR)
    if trend_atr_multiple > 2.0 and flag_atr_multiple < 1.5:
        direction = "long" if trend_move > 0 else "short"
        confidence = min(0.4 + (trend_atr_multiple - 2.0) * 0.1, 0.9)
        patterns.append(PatternMatch(
            name="flag",
            direction=direction,
            confidence=round(confidence, 2),
            description=f"{'Bull' if direction == 'long' else 'Bear'} flag: "
            f"{trend_atr_multiple:.1f}x ATR move, {flag_atr_multiple:.1f}x ATR consolidation",
        ))

    return patterns


def detect_wedge(df: pd.DataFrame, lookback: int = 15) -> list[PatternMatch]:
    """Detect rising/falling wedges via converging trendlines."""
    if len(df) < lookback:
        return []

    patterns: list[PatternMatch] = []
    section = df.iloc[-lookback:]
    x = np.arange(lookback, dtype=float)

    high_slope = np.polyfit(x, section["high"].values, 1)[0]
    low_slope = np.polyfit(x, section["low"].values, 1)[0]

    # Converging: slopes have same sign but highs converge toward lows (or vice versa)
    range_start = float(section["high"].iloc[0] - section["low"].iloc[0])
    range_end = float(section["high"].iloc[-1] - section["low"].iloc[-1])

    if range_start == 0:
        return patterns

    convergence_ratio = range_end / range_start

    # Converging wedge: range narrows significantly
    if convergence_ratio < 0.6:
        if high_slope > 0 and low_slope > 0:
            # Rising wedge (bearish)
            confidence = min(0.4 + (1.0 - convergence_ratio) * 0.3, 0.85)
            patterns.append(PatternMatch(
                name="rising_wedge",
                direction="short",
                confidence=round(confidence, 2),
                description=f"Rising wedge: range converged {convergence_ratio:.0%}",
            ))
        elif high_slope < 0 and low_slope < 0:
            # Falling wedge (bullish)
            confidence = min(0.4 + (1.0 - convergence_ratio) * 0.3, 0.85)
            patterns.append(PatternMatch(
                name="falling_wedge",
                direction="long",
                confidence=round(confidence, 2),
                description=f"Falling wedge: range converged {convergence_ratio:.0%}",
            ))

    return patterns


def detect_head_and_shoulders(
    df: pd.DataFrame,
    window: int = 3,
) -> list[PatternMatch]:
    """Detect head-and-shoulders (bearish) or inverse H&S (bullish)."""
    if len(df) < 20:
        return []

    patterns: list[PatternMatch] = []
    from packages.skills.support_resistance import find_swing_highs, find_swing_lows

    # Regular H&S (bearish)
    swing_highs = find_swing_highs(df, window)
    if len(swing_highs) >= 3:
        last_3 = swing_highs[-3:]
        vals = [float(df["high"].iloc[i]) for i in last_3]
        # Head is higher than both shoulders
        if vals[1] > vals[0] and vals[1] > vals[2]:
            symmetry = 1.0 - abs(vals[0] - vals[2]) / vals[1] if vals[1] > 0 else 0
            if symmetry > 0.85:
                confidence = min(0.3 + symmetry * 0.4, 0.8)
                patterns.append(PatternMatch(
                    name="head_and_shoulders",
                    direction="short",
                    confidence=round(confidence, 2),
                    description=f"H&S: shoulders {vals[0]:.2f}/{vals[2]:.2f}, head {vals[1]:.2f}",
                ))

    # Inverse H&S (bullish)
    swing_lows = find_swing_lows(df, window)
    if len(swing_lows) >= 3:
        last_3 = swing_lows[-3:]
        vals = [float(df["low"].iloc[i]) for i in last_3]
        if vals[1] < vals[0] and vals[1] < vals[2]:
            symmetry = 1.0 - abs(vals[0] - vals[2]) / abs(vals[1]) if vals[1] != 0 else 0
            if symmetry > 0.85:
                confidence = min(0.3 + symmetry * 0.4, 0.8)
                patterns.append(PatternMatch(
                    name="inverse_head_and_shoulders",
                    direction="long",
                    confidence=round(confidence, 2),
                    description=f"iH&S: shoulders {vals[0]:.2f}/{vals[2]:.2f}, head {vals[1]:.2f}",
                ))

    return patterns


def detect_doji(
    df: pd.DataFrame, threshold: float = 0.15, lookback: int = 5,
) -> list[PatternMatch]:
    """Detect doji candles (tiny body relative to range) in the last `lookback` bars."""
    if len(df) < lookback:
        return []

    patterns: list[PatternMatch] = []
    recent = df.iloc[-lookback:]

    for idx in range(len(recent)):
        row = recent.iloc[idx]
        total_range = float(row["high"] - row["low"])
        if total_range == 0:
            continue
        body = abs(float(row["close"] - row["open"]))
        body_ratio = body / total_range
        if body_ratio <= threshold:
            confidence = round(min(1.0 - body_ratio, 0.95), 2)
            patterns.append(PatternMatch(
                name="doji",
                direction="long",
                confidence=confidence,
                description=f"Doji: body {body_ratio:.0%} of range",
            ))

    return patterns


def detect_structure_break(
    df: pd.DataFrame, lookback: int = 20,
) -> list[PatternMatch]:
    """Detect market structure break: close above prior swing highs."""
    if len(df) < lookback + 5:
        return []

    from packages.skills.support_resistance import find_swing_highs

    patterns: list[PatternMatch] = []
    swing_highs = find_swing_highs(df.iloc[:-5], window=3)

    if len(swing_highs) < 2:
        return patterns

    prior_high = max(float(df["high"].iloc[i]) for i in swing_highs[-3:])
    last_close = float(df["close"].iloc[-1])
    atr_val = float(df["atr_14"].iloc[-1]) if "atr_14" in df.columns else 1.0

    if last_close > prior_high and atr_val > 0:
        excess = (last_close - prior_high) / atr_val
        confidence = round(min(0.5 + excess * 0.15, 0.95), 2)
        patterns.append(PatternMatch(
            name="structure_break",
            direction="long",
            confidence=confidence,
            description=f"Break above prior swing highs at {prior_high:.2f}",
        ))

    return patterns


def detect_all_patterns(df: pd.DataFrame) -> list[PatternMatch]:
    """Run all pattern detectors and return combined results."""
    patterns: list[PatternMatch] = []
    patterns.extend(detect_breakout(df))
    patterns.extend(detect_flag(df))
    patterns.extend(detect_wedge(df))
    patterns.extend(detect_head_and_shoulders(df))
    return sorted(patterns, key=lambda p: p.confidence, reverse=True)


class PatternSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "patterns"

    def analyze(self, df: pd.DataFrame, **kwargs: Any) -> list[PatternMatch]:
        return detect_all_patterns(df)
