from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx

from packages.core.models import OHLCVBar, Timeframe
from packages.core.secrets import require_secret
from packages.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_TIMEFRAME_TO_MULTIPLIER: dict[Timeframe, tuple[int, str]] = {
    Timeframe.M1: (1, "minute"),
    Timeframe.M15: (15, "minute"),
    Timeframe.M65: (65, "minute"),
    Timeframe.D1: (1, "day"),
    Timeframe.W1: (1, "week"),
}


class PolygonProvider(BaseProvider):
    """Market data provider backed by the Polygon.io REST API.

    Reads POLYGON_API_KEY from Windows Credential Manager or env vars.
    Implements rate limiting with per-request delay and exponential backoff.
    """

    BASE_URL = "https://api.polygon.io"

    def __init__(
        self,
        universe_file: Path,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        rate_limit_per_minute: int = 5,
    ) -> None:
        self._api_key = require_secret("POLYGON_API_KEY")
        self._universe_file = universe_file
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        # Delay between requests to respect rate limit
        self._request_delay = 60.0 / rate_limit_per_minute
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    async def fetch_bars(
        self, symbol: str, timeframe: Timeframe, limit: int = 390
    ) -> list[OHLCVBar]:
        multiplier, timespan = _TIMEFRAME_TO_MULTIPLIER[timeframe]

        to_date = datetime.now(tz=timezone.utc)
        if timeframe in (Timeframe.D1, Timeframe.W1):
            from_date = to_date - timedelta(days=limit * 2)
        else:
            from_date = to_date - timedelta(days=limit // 390 + 5)

        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        url = (
            f"/v2/aggs/ticker/{symbol}/range/"
            f"{multiplier}/{timespan}/{from_str}/{to_str}"
        )
        params = {
            "adjusted": "true",
            "sort": "desc",
            "limit": str(limit),
            "apiKey": self._api_key,
        }

        data = await self._request_with_retry(url, params)

        bars: list[OHLCVBar] = []
        for result in data.get("results", []):
            ts = datetime.fromtimestamp(result["t"] / 1000, tz=timezone.utc)
            bar = OHLCVBar(
                timestamp=ts,
                open=Decimal(str(result["o"])),
                high=Decimal(str(result["h"])),
                low=Decimal(str(result["l"])),
                close=Decimal(str(result["c"])),
                volume=int(result["v"]),
                timeframe=timeframe,
            )
            bars.append(bar)

        # Fetched descending to get the most recent bars; reverse to
        # return ascending order as the rest of the pipeline expects.
        bars.reverse()
        return bars[:limit]

    async def fetch_last_trade_price(self, symbol: str) -> Decimal | None:
        """Fetch the most recent price from Polygon.

        Uses /v2/aggs/ticker/{symbol}/prev (previous close), which is
        available on the free tier.  Falls back to the latest 1-minute
        bar close if prev-close is unavailable.
        """
        # Try previous-day close (free tier)
        url = f"/v2/aggs/ticker/{symbol}/prev"
        params = {"adjusted": "true", "apiKey": self._api_key}
        try:
            data = await self._request_with_retry(url, params)
            results = data.get("results", [])
            if results:
                price = results[0].get("c")
                if price is not None:
                    return Decimal(str(price))
        except Exception:
            logger.warning("Failed to fetch prev close for %s", symbol, exc_info=True)

        # Fallback: latest 1-minute bar
        try:
            bars = await self.fetch_bars(symbol, Timeframe.M1, limit=1)
            if bars:
                return bars[-1].close
        except Exception:
            logger.warning("Failed to fetch latest 1m bar for %s", symbol, exc_info=True)

        return None

    async def fetch_universe(self) -> list[str]:
        if not self._universe_file.exists():
            raise FileNotFoundError(
                f"Universe file not found: {self._universe_file}. "
                f"Expected file at {self._universe_file.resolve()}."
            )

        symbols: list[str] = []
        with open(self._universe_file) as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    symbols.append(stripped.upper())
        return symbols

    async def _request_with_retry(
        self, url: str, params: dict[str, str]
    ) -> dict:  # type: ignore[type-arg]
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            # Rate limit: wait between requests
            await asyncio.sleep(self._request_delay)
            try:
                response = await self._client.get(url, params=params)
                if response.status_code == 429:
                    wait = self._backoff_seconds * (2 ** (attempt + 1))
                    logger.warning(
                        "Rate limited on %s, waiting %.1fs", url.split("?")[0], wait
                    )
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                # Redact API key from error logs
                logger.warning(
                    "Request failed for %s (attempt %d/%d): %s",
                    url.split("?")[0],
                    attempt + 1,
                    self._max_retries,
                    exc.response.status_code,
                )
                wait = self._backoff_seconds * (2**attempt)
                await asyncio.sleep(wait)
            except httpx.TransportError as exc:
                last_exc = exc
                wait = self._backoff_seconds * (2**attempt)
                await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]
