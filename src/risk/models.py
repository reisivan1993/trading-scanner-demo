from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Direction(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class Setup:
    """Immutable trade setup produced by the scanning engine."""

    ticker: str
    direction: Direction
    entry: Decimal
    stop: Decimal
    target: Decimal
    score: int  # 0-100 quality score

    @property
    def risk_per_share(self) -> Decimal:
        return abs(self.entry - self.stop)

    @property
    def reward_per_share(self) -> Decimal:
        return abs(self.target - self.entry)

    @property
    def rr_ratio(self) -> Decimal:
        risk = self.risk_per_share
        if risk == 0:
            return Decimal("0")
        return self.reward_per_share / risk

    def position_size(self, capital: Decimal) -> int:
        """Number of shares for the given capital allocation."""
        if self.entry == 0:
            return 0
        return int(capital / self.entry)

    def expected_profit(self, capital: Decimal) -> Decimal:
        """Expected profit in dollars if target is hit."""
        shares = self.position_size(capital)
        return self.reward_per_share * shares

    def expected_loss(self, capital: Decimal) -> Decimal:
        """Expected loss in dollars if stop is hit."""
        shares = self.position_size(capital)
        return self.risk_per_share * shares
