from __future__ import annotations

from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from packages.core.models import (
    BarVolumeCondition,
    BreakoutValidity,
    VolumeAnalysisResult,
    VolumeConditionTag,
    VolumeDivergence,
    VSAPatternTag,
    VSASignal,
)
from packages.skills.base import BaseSkill

DEFAULT_VOL_LOOKBACK = 20
DEFAULT_SPREAD_LOOKBACK = 20
DEFAULT_HIGH_VOL_MULT = 1.5
DEFAULT_EXTREME_VOL_MULT = 2.5
DEFAULT_LOW_VOL_MULT = 0.7
DEFAULT_STRONG_THR = 0.75
DEFAULT_WEAK_THR = 0.25
DEFAULT_WICK_THR = 0.3
DEFAULT_CONFIRM_BARS = 1
_TINY = 1e-10

DEFAULTS: dict[str, Any] = {
    "vol_lookback": DEFAULT_VOL_LOOKBACK,
    "spread_lookback": DEFAULT_SPREAD_LOOKBACK,
    "high_vol_mult": DEFAULT_HIGH_VOL_MULT,
    "extreme_vol_mult": DEFAULT_EXTREME_VOL_MULT,
    "low_vol_mult": DEFAULT_LOW_VOL_MULT,
    "strong_thr": DEFAULT_STRONG_THR,
    "weak_thr": DEFAULT_WEAK_THR,
    "wick_thr": DEFAULT_WICK_THR,
    "confirm_bars": DEFAULT_CONFIRM_BARS,
}


def _bar_metrics(row: pd.Series, vol_avg: float, spread_avg: float) -> dict[str, float]:
    spread = float(row["high"]) - float(row["low"])
    close_pos = (float(row["close"]) - float(row["low"])) / max(spread, _TINY)
    vol_rel = float(row["volume"]) / max(vol_avg, _TINY)
    spread_rel = spread / max(spread_avg, _TINY)
    lower_wick = min(float(row["open"]), float(row["close"])) - float(row["low"])
    upper_wick = float(row["high"]) - max(float(row["open"]), float(row["close"]))
    lower_wick_rel = lower_wick / max(spread, _TINY)
    upper_wick_rel = upper_wick / max(spread, _TINY)
    return {
        "spread": spread,
        "close_pos": close_pos,
        "vol_rel": vol_rel,
        "spread_rel": spread_rel,
        "lower_wick": lower_wick,
        "upper_wick": upper_wick,
        "lower_wick_rel": lower_wick_rel,
        "upper_wick_rel": upper_wick_rel,
    }


def classify_volume_condition(
    vol_rel: float,
    spread_rel: float,
    close_pos: float,
    params: dict[str, Any],
) -> VolumeConditionTag:
    high_vol_mult = params["high_vol_mult"]
    low_vol_mult = params["low_vol_mult"]
    strong_thr = params["strong_thr"]

    if vol_rel >= high_vol_mult and spread_rel >= 1.2 and close_pos >= strong_thr:
        return VolumeConditionTag.HEALTHY_MOVE
    if vol_rel >= high_vol_mult and spread_rel < 1.0:
        return VolumeConditionTag.EFFORT_NO_RESULT
    if vol_rel <= low_vol_mult and spread_rel < 0.8 and close_pos >= 0.5:
        return VolumeConditionTag.NO_SUPPLY
    if vol_rel <= low_vol_mult and spread_rel < 0.8 and close_pos < 0.5:
        return VolumeConditionTag.NO_DEMAND
    return VolumeConditionTag.NEUTRAL


def detect_stopping_volume(
    df: pd.DataFrame,
    vol_avg: pd.Series,
    spread_avg: pd.Series,
    params: dict[str, Any],
) -> list[VSASignal]:
    signals: list[VSASignal] = []
    extreme_vol_mult = params["extreme_vol_mult"]
    wick_thr = params["wick_thr"]
    confirm_bars = params["confirm_bars"]
    vol_lookback = params["vol_lookback"]

    for i in range(vol_lookback, len(df)):
        row = df.iloc[i]
        metrics = _bar_metrics(row, float(vol_avg.iloc[i]), float(spread_avg.iloc[i]))

        # Context gate: must be in downtrend (close < ema_20)
        if "ema_20" in df.columns and float(row["close"]) >= float(row["ema_20"]):
            continue

        if metrics["vol_rel"] < extreme_vol_mult:
            continue
        if metrics["lower_wick_rel"] < wick_thr:
            continue
        if metrics["close_pos"] < 0.4:
            continue

        # Optional confirmation: next bar closes above this bar's low
        if (
            confirm_bars >= 1
            and i + 1 < len(df)
            and float(df.iloc[i + 1]["close"]) <= float(row["low"])
        ):
            continue

        vol_ratio = metrics["vol_rel"] / extreme_vol_mult
        confidence = min(1.0, vol_ratio * 0.5 + metrics["close_pos"] * 0.5)
        signals.append(VSASignal(
            pattern=VSAPatternTag.STOPPING_VOLUME,
            bar_index=i,
            direction="bullish",
            confidence=round(confidence, 4),
            description=(
                f"Stopping volume at bar {i}: "
                f"vol_rel={metrics['vol_rel']:.2f}, close_pos={metrics['close_pos']:.2f}"
            ),
        ))

    return signals


def detect_buying_climax(
    df: pd.DataFrame,
    vol_avg: pd.Series,
    spread_avg: pd.Series,
    params: dict[str, Any],
) -> list[VSASignal]:
    signals: list[VSASignal] = []
    extreme_vol_mult = params["extreme_vol_mult"]
    weak_thr = params["weak_thr"]
    wick_thr = params["wick_thr"]
    vol_lookback = params["vol_lookback"]

    for i in range(vol_lookback, len(df)):
        row = df.iloc[i]
        metrics = _bar_metrics(row, float(vol_avg.iloc[i]), float(spread_avg.iloc[i]))

        # Context gate: must be in uptrend (close > ema_20)
        if "ema_20" in df.columns and float(row["close"]) <= float(row["ema_20"]):
            continue

        if metrics["vol_rel"] < extreme_vol_mult:
            continue
        if not (metrics["close_pos"] <= weak_thr or metrics["upper_wick_rel"] >= wick_thr):
            continue

        vol_ratio = metrics["vol_rel"] / extreme_vol_mult
        confidence = min(1.0, vol_ratio * 0.5 + (1.0 - metrics["close_pos"]) * 0.5)
        signals.append(VSASignal(
            pattern=VSAPatternTag.BUYING_CLIMAX,
            bar_index=i,
            direction="bearish",
            confidence=round(confidence, 4),
            description=(
                f"Buying climax at bar {i}: "
                f"vol_rel={metrics['vol_rel']:.2f}, close_pos={metrics['close_pos']:.2f}"
            ),
        ))

    return signals


def detect_no_supply_test(
    df: pd.DataFrame,
    vol_avg: pd.Series,
    spread_avg: pd.Series,
    params: dict[str, Any],
) -> list[VSASignal]:
    signals: list[VSASignal] = []
    low_vol_mult = params["low_vol_mult"]
    vol_lookback = params["vol_lookback"]

    for i in range(vol_lookback, len(df)):
        row = df.iloc[i]
        metrics = _bar_metrics(row, float(vol_avg.iloc[i]), float(spread_avg.iloc[i]))

        if metrics["vol_rel"] > low_vol_mult:
            continue
        if metrics["spread_rel"] >= 0.8:
            continue
        if metrics["close_pos"] < 0.5:
            continue

        confidence = min(1.0, (1.0 - metrics["vol_rel"]) * 0.6 + metrics["close_pos"] * 0.4)
        signals.append(VSASignal(
            pattern=VSAPatternTag.NO_SUPPLY_TEST,
            bar_index=i,
            direction="bullish",
            confidence=round(confidence, 4),
            description=(
                f"No supply test at bar {i}: "
                f"vol_rel={metrics['vol_rel']:.2f}, close_pos={metrics['close_pos']:.2f}"
            ),
        ))

    return signals


def detect_no_demand_test(
    df: pd.DataFrame,
    vol_avg: pd.Series,
    spread_avg: pd.Series,
    params: dict[str, Any],
) -> list[VSASignal]:
    signals: list[VSASignal] = []
    low_vol_mult = params["low_vol_mult"]
    vol_lookback = params["vol_lookback"]

    for i in range(vol_lookback, len(df)):
        row = df.iloc[i]
        metrics = _bar_metrics(row, float(vol_avg.iloc[i]), float(spread_avg.iloc[i]))

        if metrics["vol_rel"] > low_vol_mult:
            continue
        if metrics["spread_rel"] >= 0.8:
            continue
        if metrics["close_pos"] >= 0.5:
            continue

        confidence = min(1.0, (1.0 - metrics["vol_rel"]) * 0.6 + (1.0 - metrics["close_pos"]) * 0.4)
        signals.append(VSASignal(
            pattern=VSAPatternTag.NO_DEMAND_TEST,
            bar_index=i,
            direction="bearish",
            confidence=round(confidence, 4),
            description=(
                f"No demand test at bar {i}: "
                f"vol_rel={metrics['vol_rel']:.2f}, close_pos={metrics['close_pos']:.2f}"
            ),
        ))

    return signals


def detect_vsa_patterns(df: pd.DataFrame, params: dict[str, Any]) -> list[VSASignal]:
    vol_lookback = params["vol_lookback"]
    spread_lookback = params["spread_lookback"]

    vol_avg = df["volume"].rolling(window=vol_lookback, min_periods=1).mean()
    spread_avg = (df["high"] - df["low"]).rolling(window=spread_lookback, min_periods=1).mean()

    signals: list[VSASignal] = []
    signals.extend(detect_stopping_volume(df, vol_avg, spread_avg, params))
    signals.extend(detect_buying_climax(df, vol_avg, spread_avg, params))
    signals.extend(detect_no_supply_test(df, vol_avg, spread_avg, params))
    signals.extend(detect_no_demand_test(df, vol_avg, spread_avg, params))

    return sorted(signals, key=lambda s: s.bar_index)


def detect_volume_divergences(df: pd.DataFrame, params: dict[str, Any]) -> list[VolumeDivergence]:
    vol_lookback = params["vol_lookback"]
    n = max(vol_lookback, 10)

    if len(df) < n:
        return []

    close_vals = df["close"].astype(float).values[-n:]
    vol_vals = df["volume"].astype(float).values[-n:]
    x = np.arange(n, dtype=float)

    price_slope = float(np.polyfit(x, close_vals, 1)[0])
    vol_slope = float(np.polyfit(x, vol_vals, 1)[0])

    divergences: list[VolumeDivergence] = []

    if price_slope < 0 and vol_slope < 0:
        confidence = min(1.0, abs(vol_slope / (abs(price_slope) + _TINY)))
        divergences.append(VolumeDivergence(
            divergence_type="bullish",
            lookback_bars=n,
            confidence=round(confidence, 4),
            description="Price declining on shrinking volume — selling exhaustion",
        ))
    elif price_slope > 0 and vol_slope < 0:
        confidence = min(1.0, abs(vol_slope / (abs(price_slope) + _TINY)))
        divergences.append(VolumeDivergence(
            divergence_type="bearish",
            lookback_bars=n,
            confidence=round(confidence, 4),
            description="Price rising on shrinking volume — buying exhaustion",
        ))

    return divergences


def detect_breakout_validity(
    df: pd.DataFrame,
    key_levels: list[float | Decimal],
    params: dict[str, Any],
) -> list[BreakoutValidity]:
    if len(df) < 2:
        return []

    high_vol_mult = params["high_vol_mult"]
    vol_lookback = params["vol_lookback"]
    spread_lookback = params["spread_lookback"]

    vol_avg = float(
        df["volume"].rolling(window=vol_lookback, min_periods=1).mean().iloc[-1]
    )
    spread_avg = float(
        (df["high"] - df["low"]).rolling(window=spread_lookback, min_periods=1).mean().iloc[-1]
    )

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    current_close = float(last_row["close"])
    prev_close = float(prev_row["close"])

    metrics = _bar_metrics(last_row, vol_avg, spread_avg)
    is_valid = metrics["vol_rel"] >= high_vol_mult and metrics["spread_rel"] >= 1.2

    breakouts: list[BreakoutValidity] = []

    for raw_level in key_levels:
        level_f = float(raw_level)

        if current_close > level_f and prev_close <= level_f:
            direction: str = "long"
        elif current_close < level_f and prev_close >= level_f:
            direction = "short"
        else:
            continue

        vr = metrics["vol_rel"]
        sr = metrics["spread_rel"]
        if is_valid:
            reason = (
                f"Valid breakout: vol_rel={vr:.2f} >= {high_vol_mult}, spread_rel={sr:.2f} >= 1.2"
            )
        elif vr < high_vol_mult and sr < 1.2:
            reason = f"Invalid: vol_rel={vr:.2f} < {high_vol_mult} and spread_rel={sr:.2f} < 1.2"
        elif vr < high_vol_mult:
            reason = f"Invalid: vol_rel={vr:.2f} < {high_vol_mult}"
        else:
            reason = f"Invalid: spread_rel={sr:.2f} < 1.2"

        breakouts.append(BreakoutValidity(
            level=Decimal(str(raw_level)),
            direction=direction,  # type: ignore[arg-type]
            is_valid=is_valid,
            vol_rel=round(vr, 4),
            spread_rel=round(sr, 4),
            reason=reason,
        ))

    return breakouts


def compute_volume_bias(
    conditions: list[BarVolumeCondition],
    signals: list[VSASignal],
    divergences: list[VolumeDivergence],
    breakouts: list[BreakoutValidity],
) -> tuple[str, float, list[str]]:
    bullish_pts = 0.0
    bearish_pts = 0.0
    reasons: list[str] = []

    for sig in signals:
        pts = sig.confidence * 0.35
        if sig.direction == "bullish":
            bullish_pts += pts
            reasons.append(
                f"Bullish VSA signal: {sig.pattern.value} (confidence={sig.confidence:.2f})"
            )
        else:
            bearish_pts += pts
            reasons.append(
                f"Bearish VSA signal: {sig.pattern.value} (confidence={sig.confidence:.2f})"
            )

    for div in divergences:
        pts = div.confidence * 0.25
        if div.divergence_type == "bullish":
            bullish_pts += pts
            reasons.append(
                f"Bullish divergence: {div.description} (confidence={div.confidence:.2f})"
            )
        else:
            bearish_pts += pts
            reasons.append(
                f"Bearish divergence: {div.description} (confidence={div.confidence:.2f})"
            )

    for bo in breakouts:
        if not bo.is_valid:
            continue
        if bo.direction == "long":
            bullish_pts += 0.30
            reasons.append(f"Valid long breakout at {bo.level}")
        else:
            bearish_pts += 0.30
            reasons.append(f"Valid short breakout at {bo.level}")

    if conditions:
        last_condition = conditions[-1]
        if last_condition.condition == VolumeConditionTag.HEALTHY_MOVE:
            if bullish_pts >= bearish_pts:
                bullish_pts += 0.15
                reasons.append("Last bar healthy move (bullish)")
            else:
                bearish_pts += 0.15
                reasons.append("Last bar healthy move (bearish)")
        elif last_condition.condition == VolumeConditionTag.EFFORT_NO_RESULT:
            if bullish_pts >= bearish_pts:
                bearish_pts += 0.15
                reasons.append("Last bar effort with no result (bearish pressure on rally)")
            else:
                bullish_pts += 0.15
                reasons.append("Last bar effort with no result (bullish pressure on decline)")

    total = bullish_pts + bearish_pts
    if total == 0.0:
        return "neutral", 0.0, reasons

    if bullish_pts > bearish_pts:
        bias = "bullish"
    elif bearish_pts > bullish_pts:
        bias = "bearish"
    else:
        bias = "neutral"

    confidence = min(1.0, abs(bullish_pts - bearish_pts) / total)
    return bias, round(confidence, 4), reasons


def analyze_volume(
    df: pd.DataFrame,
    key_levels: list[float | Decimal],
    params: dict[str, Any],
) -> VolumeAnalysisResult:
    vol_lookback = params["vol_lookback"]
    spread_lookback = params["spread_lookback"]

    empty_result = VolumeAnalysisResult(
        conditions=[],
        vsa_signals=[],
        divergences=[],
        breakout_signals=[],
        bias="neutral",
        confidence=0.0,
        reasons=[],
    )

    if len(df) < vol_lookback:
        return empty_result

    vol_avg = df["volume"].rolling(window=vol_lookback, min_periods=1).mean()
    spread_avg = (df["high"] - df["low"]).rolling(window=spread_lookback, min_periods=1).mean()

    conditions: list[BarVolumeCondition] = []
    for i in range(vol_lookback, len(df)):
        row = df.iloc[i]
        metrics = _bar_metrics(row, float(vol_avg.iloc[i]), float(spread_avg.iloc[i]))
        tag = classify_volume_condition(
            metrics["vol_rel"],
            metrics["spread_rel"],
            metrics["close_pos"],
            params,
        )
        conditions.append(BarVolumeCondition(
            bar_index=i,
            vol_rel=round(metrics["vol_rel"], 4),
            spread_rel=round(metrics["spread_rel"], 4),
            close_pos=round(metrics["close_pos"], 4),
            condition=tag,
        ))

    vsa_signals = detect_vsa_patterns(df, params)
    divergences = detect_volume_divergences(df, params)
    breakout_signals = detect_breakout_validity(df, key_levels, params)
    bias, confidence, reasons = compute_volume_bias(
        conditions, vsa_signals, divergences, breakout_signals
    )

    return VolumeAnalysisResult(
        conditions=conditions,
        vsa_signals=vsa_signals,
        divergences=divergences,
        breakout_signals=breakout_signals,
        bias=bias,  # type: ignore[arg-type]
        confidence=confidence,
        reasons=reasons,
    )


class VolumeAnalysisSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "volume_analysis"

    def analyze(self, df: pd.DataFrame, **kwargs: Any) -> VolumeAnalysisResult:
        key_levels = kwargs.get("key_levels", [])
        params = {k: kwargs.get(k, default) for k, default in DEFAULTS.items()}
        return analyze_volume(df, key_levels, params)
