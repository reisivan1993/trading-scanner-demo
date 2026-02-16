from __future__ import annotations

from packages.core.models import OHLCVBar, Timeframe
from packages.providers.base import BaseProvider


class AlpacaProvider(BaseProvider):
    """Placeholder provider for the Alpaca Markets API.

    Not yet implemented. All methods raise NotImplementedError.
    """

    async def fetch_bars(
        self, symbol: str, timeframe: Timeframe, limit: int = 390
    ) -> list[OHLCVBar]:
        """Not implemented."""
        raise NotImplementedError("Alpaca provider not yet implemented")

    async def fetch_universe(self) -> list[str]:
        """Not implemented."""
        raise NotImplementedError("Alpaca provider not yet implemented")
