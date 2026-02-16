from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from packages.core.models import OHLCVBar, Timeframe


class BaseProvider(ABC):
    """Abstract base class for all market data providers."""

    @abstractmethod
    async def fetch_bars(
        self, symbol: str, timeframe: Timeframe, limit: int = 390
    ) -> list[OHLCVBar]:
        """Fetch OHLCV bars for a given symbol and timeframe.

        Args:
            symbol: Ticker symbol (e.g. "AAPL").
            timeframe: Bar timeframe (e.g. Timeframe.D1).
            limit: Maximum number of bars to return.

        Returns:
            List of OHLCVBar objects sorted by timestamp ascending.
        """
        ...

    @abstractmethod
    async def fetch_universe(self) -> list[str]:
        """Load the list of ticker symbols to scan.

        Returns:
            List of uppercase ticker symbols.
        """
        ...

    async def fetch_last_trade_price(self, symbol: str) -> Decimal | None:
        """Fetch the most recent trade price for a symbol.

        Returns:
            The last trade price, or None if unavailable.
        """
        return None
