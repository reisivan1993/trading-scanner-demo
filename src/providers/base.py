from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, Sequence


@dataclass(frozen=True)
class Candle:
    """Immutable OHLCV candle for a single trading day."""

    ticker: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class DataProvider(Protocol):
    """Protocol that all market data providers must implement."""

    async def get_daily_candles(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> Sequence[Candle]:
        """Fetch daily candles for a ticker in the given date range."""
        ...

    async def get_bulk_candles(
        self,
        tickers: Sequence[str],
        start: date,
        end: date,
    ) -> dict[str, Sequence[Candle]]:
        """Fetch daily candles for multiple tickers. Returns {ticker: candles}."""
        ...
