from __future__ import annotations

import math
from decimal import Decimal
from typing import Literal

from packages.core.models import SRZone, TradeSetup


def _find_nearest_zone(
    zones: list[SRZone],
    zone_type: str,
    reference_price: float,
    direction: str,
) -> Decimal | None:
    """Find the nearest S/R zone of given type suitable for the trade direction."""
    candidates = [z for z in zones if z.zone_type == zone_type]
    if not candidates:
        return None

    if direction == "long" and zone_type == "support":
        # Support below entry for long stop
        below = [z for z in candidates if float(z.price) < reference_price]
        if below:
            return max(below, key=lambda z: float(z.price)).price
    elif direction == "long" and zone_type == "resistance":
        # Resistance above entry for long target
        above = [z for z in candidates if float(z.price) > reference_price]
        if above:
            return min(above, key=lambda z: float(z.price)).price
    elif direction == "short" and zone_type == "resistance":
        # Resistance above entry for short stop
        above = [z for z in candidates if float(z.price) > reference_price]
        if above:
            return min(above, key=lambda z: float(z.price)).price
    elif direction == "short" and zone_type == "support":
        # Support below entry for short target
        below = [z for z in candidates if float(z.price) < reference_price]
        if below:
            return max(below, key=lambda z: float(z.price)).price

    return None


def generate_setup(
    symbol: str,
    direction: Literal["long", "short"],
    entry_price: float,
    atr: float,
    position_size_usd: int,
    sr_zones: list[SRZone] | None = None,
    stop_override: float | None = None,
    target_1_override: float | None = None,
    target_2_override: float | None = None,
) -> TradeSetup:
    """Generate a trade setup with entry, stop, targets, shares, and P&L.

    Stop/target logic:
    - First tries S/R zones for placement
    - Falls back to ATR-based levels (1.5 ATR stop, 2x/3x ATR targets)
    """
    _zones = sr_zones or []
    entry = Decimal(str(round(entry_price, 2)))

    # Determine stop
    if stop_override is not None:
        stop = Decimal(str(round(stop_override, 2)))
    else:
        zone_stop = _find_nearest_zone(
            _zones,
            "support" if direction == "long" else "resistance",
            entry_price,
            direction,
        )
        if zone_stop is not None:
            stop = zone_stop
        elif direction == "long":
            stop = Decimal(str(round(entry_price - 1.5 * atr, 2)))
        else:
            stop = Decimal(str(round(entry_price + 1.5 * atr, 2)))

    # Determine targets
    if target_1_override is not None:
        target_1 = Decimal(str(round(target_1_override, 2)))
    else:
        zone_t1 = _find_nearest_zone(
            _zones,
            "resistance" if direction == "long" else "support",
            entry_price,
            direction,
        )
        if zone_t1 is not None:
            target_1 = zone_t1
        elif direction == "long":
            target_1 = Decimal(str(round(entry_price + 2.0 * atr, 2)))
        else:
            target_1 = Decimal(str(round(entry_price - 2.0 * atr, 2)))

    if target_2_override is not None:
        target_2 = Decimal(str(round(target_2_override, 2)))
    else:
        if direction == "long":
            target_2 = Decimal(str(round(entry_price + 3.0 * atr, 2)))
        else:
            target_2 = Decimal(str(round(entry_price - 3.0 * atr, 2)))

    # Calculate risk and shares
    risk_per_share = abs(entry - stop)
    if risk_per_share == 0:
        risk_per_share = Decimal("0.01")

    shares = math.floor(position_size_usd / float(entry)) if float(entry) > 0 else 0
    dollar_risk = risk_per_share * shares

    # R:R ratio
    reward_per_share = abs(target_1 - entry)
    rr_ratio = float(reward_per_share / risk_per_share) if risk_per_share > 0 else 0.0

    # P&L calculations
    dollar_pnl_t1 = reward_per_share * shares
    dollar_pnl_t2 = abs(target_2 - entry) * shares

    return TradeSetup(
        symbol=symbol,
        direction=direction,
        entry=entry,
        stop=stop,
        target_1=target_1,
        target_2=target_2,
        rr_ratio=round(rr_ratio, 2),
        shares=shares,
        dollar_risk=dollar_risk,
        dollar_pnl_t1=dollar_pnl_t1,
        dollar_pnl_t2=dollar_pnl_t2,
    )
