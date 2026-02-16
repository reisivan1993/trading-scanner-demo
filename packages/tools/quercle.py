from __future__ import annotations

import logging
from typing import Any

import httpx

from packages.core.secrets import get_secret

logger = logging.getLogger(__name__)

BASE_URL = "https://api.quercle.com/v1/search"


class QuercleTool:
    """Wrapper for the Quercle web intelligence API."""

    def __init__(self, lookback_days: int = 3) -> None:
        self.lookback_days = lookback_days
        self._api_key: str | None = None

    def _get_api_key(self) -> str:
        if self._api_key is None:
            key = get_secret("QUERCLE_API_KEY")
            if not key:
                raise EnvironmentError("QUERCLE_API_KEY not found in vault or environment")
            self._api_key = key
        return self._api_key

    async def search(self, symbol: str, intent: str) -> list[dict[str, Any]]:
        """Search Quercle for web intelligence on a symbol.

        Returns list of result dicts with: title, snippet, source, published_at, sentiment.
        Gracefully returns empty list on any failure.
        """
        try:
            api_key = self._get_api_key()
        except EnvironmentError:
            logger.warning("Quercle API key not configured")
            return []

        params = {
            "symbol": symbol,
            "intent": intent,
            "lookback_days": self.lookback_days,
        }
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(BASE_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data.get("results", [])
        except Exception:
            logger.warning("Quercle search failed for %s", symbol, exc_info=True)
            return []
