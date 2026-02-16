from __future__ import annotations

from decimal import Decimal
from typing import Literal

import pandas as pd

from packages.core.models import ChecklistItem, SRZone


def evaluate_checklist(
    df_1d: pd.DataFrame,
    df_1w: pd.DataFrame,
    sr_zones: list[SRZone],
    direction: Literal["long", "short"],
    entry_price: float,
) -> list[ChecklistItem]:
    """Evaluate all 7 checklist criteria and return results."""
    return [
        _check_clear_direction(df_1d, direction),
        _check_weekly_trend(df_1w, direction),
        _check_volume_confirms(df_1d),
        _check_price_vs_sma20(df_1d, direction),
        _check_gap_structure(df_1d, direction),
        _check_nearby_sr(sr_zones, entry_price),
        _check_cci_in_range(df_1d),
    ]


def _check_clear_direction(
    df: pd.DataFrame, direction: Literal["long", "short"],
) -> ChecklistItem:
    """EMA 9 > 20 > 50 (long) or 9 < 20 < 50 (short)."""
    required = ["ema_9", "ema_20", "ema_50"]
    if df.empty or not all(col in df.columns for col in required):
        return ChecklistItem(
            criterion="Clear Direction",
            passed=False,
            notes="Insufficient EMA data",
        )

    last = df.iloc[-1]
    ema9, ema20, ema50 = last["ema_9"], last["ema_20"], last["ema_50"]

    if direction == "long":
        passed = ema9 > ema20 > ema50
        label = "bullish"
    else:
        passed = ema9 < ema20 < ema50
        label = "bearish"

    return ChecklistItem(
        criterion="Clear Direction",
        passed=bool(passed),
        value=f"EMA 9/20/50 {label}",
        notes=f"9={ema9:.2f} 20={ema20:.2f} 50={ema50:.2f}",
    )


def _check_weekly_trend(
    df_1w: pd.DataFrame, direction: Literal["long", "short"],
) -> ChecklistItem:
    """Weekly close vs weekly EMA 20."""
    if df_1w.empty or "ema_20" not in df_1w.columns:
        return ChecklistItem(
            criterion="Weekly Trend Alignment",
            passed=False,
            notes="No weekly data",
        )

    last = df_1w.iloc[-1]
    close = last["close"]
    wk_ema20 = last["ema_20"]

    if direction == "long":
        passed = close > wk_ema20
    else:
        passed = close < wk_ema20

    return ChecklistItem(
        criterion="Weekly Trend Alignment",
        passed=bool(passed),
        value=f"Close={close:.2f} vs EMA20={wk_ema20:.2f}",
    )


def _check_volume_confirms(df: pd.DataFrame) -> ChecklistItem:
    """RVOL >= 1.0 on last bar."""
    if df.empty or "rvol_20" not in df.columns:
        return ChecklistItem(
            criterion="Volume Confirms Trend",
            passed=False,
            notes="No RVOL data",
        )

    rvol_val = float(df["rvol_20"].iloc[-1])
    passed = rvol_val >= 1.0

    return ChecklistItem(
        criterion="Volume Confirms Trend",
        passed=passed,
        value=f"RVOL {rvol_val:.2f}x",
    )


def _check_price_vs_sma20(
    df: pd.DataFrame, direction: Literal["long", "short"],
) -> ChecklistItem:
    """Close > SMA 20 (long) or < SMA 20 (short)."""
    if df.empty or "sma_20" not in df.columns:
        return ChecklistItem(
            criterion="Price vs 20 MA",
            passed=False,
            notes="No SMA 20 data",
        )

    last = df.iloc[-1]
    close = last["close"]
    sma_val = last["sma_20"]

    if direction == "long":
        passed = close > sma_val
    else:
        passed = close < sma_val

    return ChecklistItem(
        criterion="Price vs 20 MA",
        passed=bool(passed),
        value=f"Close={close:.2f} SMA20={sma_val:.2f}",
    )


def _check_gap_structure(
    df: pd.DataFrame, direction: Literal["long", "short"],
) -> ChecklistItem:
    """Detect gap up/down on last bar(s)."""
    if df.empty or len(df) < 2:
        return ChecklistItem(
            criterion="Gap Structure",
            passed=False,
            notes="Insufficient data",
        )

    prev_close = df["close"].iloc[-2]
    curr_open = df["open"].iloc[-1]

    if prev_close == 0:
        return ChecklistItem(
            criterion="Gap Structure",
            passed=False,
            notes="Previous close is zero",
        )

    gap_pct = ((curr_open - prev_close) / prev_close) * 100

    has_gap_up = gap_pct > 0.5
    has_gap_down = gap_pct < -0.5

    if direction == "long":
        passed = has_gap_up
        label = f"Gap {'up' if has_gap_up else 'down' if has_gap_down else 'none'}"
    else:
        passed = has_gap_down
        label = f"Gap {'down' if has_gap_down else 'up' if has_gap_up else 'none'}"

    return ChecklistItem(
        criterion="Gap Structure",
        passed=passed,
        value=f"{label} ({gap_pct:+.2f}%)",
    )


def _check_nearby_sr(
    sr_zones: list[SRZone], entry_price: float,
) -> ChecklistItem:
    """S/R zone within 3% of entry price."""
    if not sr_zones or entry_price <= 0:
        return ChecklistItem(
            criterion="Nearby S/R",
            passed=False,
            notes="No S/R zones available",
        )

    threshold = entry_price * 0.03
    nearby = [
        z for z in sr_zones
        if abs(float(z.price) - entry_price) <= threshold
    ]

    if nearby:
        closest = min(nearby, key=lambda z: abs(float(z.price) - entry_price))
        distance_pct = ((float(closest.price) - entry_price) / entry_price) * 100
        return ChecklistItem(
            criterion="Nearby S/R",
            passed=True,
            value=f"${closest.price} ({closest.zone_type})",
            notes=f"{distance_pct:+.1f}% away",
        )

    return ChecklistItem(
        criterion="Nearby S/R",
        passed=False,
        value="No zone within 3%",
    )


def _check_cci_in_range(df: pd.DataFrame) -> ChecklistItem:
    """CCI between -100 and +100."""
    if df.empty or "cci_20" not in df.columns:
        return ChecklistItem(
            criterion="CCI in Range",
            passed=False,
            notes="No CCI data",
        )

    cci_val = float(df["cci_20"].iloc[-1])
    passed = -100 <= cci_val <= 100

    return ChecklistItem(
        criterion="CCI in Range",
        passed=passed,
        value=f"CCI {cci_val:.1f}",
        notes="" if passed else "Outside -100 to +100 range",
    )
