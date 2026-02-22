from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import yfinance as yf

from packages.core.models import OHLCVBar, Timeframe
from packages.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Map our Timeframe enum to yfinance interval strings
_TIMEFRAME_TO_YF_INTERVAL: dict[Timeframe, str] = {
    Timeframe.M1: "1m",
    Timeframe.M15: "15m",
    Timeframe.M65: "60m",  # yfinance doesn't support 65m; closest is 60m
    Timeframe.D1: "1d",
    Timeframe.W1: "1wk",
}

# yfinance limits lookback by interval; these are safe defaults
_TIMEFRAME_TO_YF_PERIOD: dict[Timeframe, str] = {
    Timeframe.M1: "7d",      # 1m data: max 7 days
    Timeframe.M15: "60d",    # 15m data: max 60 days
    Timeframe.M65: "60d",    # 60m data: max 60 days (using as proxy for 65m)
    Timeframe.D1: "1y",      # daily: 1 year
    Timeframe.W1: "2y",      # weekly: 2 years
}


class YFinanceProvider(BaseProvider):
    """Market data provider using yfinance (Yahoo/Google Finance data).

    Free, no API key required. Suitable for moderate-volume scanning.
    """

    def __init__(
        self,
        universe_file: Path,
        rate_limit_per_minute: int = 60,
    ) -> None:
        self._universe_file = universe_file
        self._request_delay = 60.0 / rate_limit_per_minute

    @staticmethod
    def _clean_symbol(symbol: str) -> str:
        """Strip exchange prefix if present (e.g. 'NASDAQ:AAPL' -> 'AAPL').

        Also handles special TradingView symbols that yfinance can't fetch.
        """
        if ":" in symbol:
            symbol = symbol.split(":", 1)[1]
        # Remove TradingView continuous-contract suffixes like "CL1!"
        symbol = symbol.rstrip("!")
        return symbol

    async def fetch_bars(
        self, symbol: str, timeframe: Timeframe, limit: int = 390
    ) -> list[OHLCVBar]:
        """Fetch OHLCV bars from Yahoo Finance."""
        clean = self._clean_symbol(symbol)
        interval = _TIMEFRAME_TO_YF_INTERVAL[timeframe]
        period = _TIMEFRAME_TO_YF_PERIOD[timeframe]

        # Run the blocking yfinance call in a thread pool
        loop = asyncio.get_event_loop()
        try:
            df = await loop.run_in_executor(
                None,
                lambda: yf.download(
                    clean,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=True,
                ),
            )
        except Exception as exc:
            logger.warning("yfinance fetch failed for %s: %s", clean, exc)
            return []

        if df is None or df.empty:
            logger.info("No data returned from yfinance for %s (%s)", clean, interval)
            return []

        # Rate-limit between requests
        await asyncio.sleep(self._request_delay)

        bars: list[OHLCVBar] = []
        for ts, row in df.iterrows():
            try:
                bar = OHLCVBar(
                    timestamp=ts.to_pydatetime().replace(tzinfo=timezone.utc),
                    open=Decimal(str(float(row["Open"]))),
                    high=Decimal(str(float(row["High"]))),
                    low=Decimal(str(float(row["Low"]))),
                    close=Decimal(str(float(row["Close"]))),
                    volume=int(float(row["Volume"])),
                    timeframe=timeframe,
                )
                bars.append(bar)
            except (ValueError, KeyError) as exc:
                logger.debug("Skipping bar for %s: %s", clean, exc)
                continue

        # Return in ascending order, capped at limit
        return bars[-limit:]

    async def fetch_last_trade_price(self, symbol: str) -> Decimal | None:
        """Fetch the most recent closing price from Yahoo Finance."""
        clean = self._clean_symbol(symbol)

        loop = asyncio.get_event_loop()
        try:
            ticker = await loop.run_in_executor(
                None, lambda: yf.Ticker(clean)
            )
            info = await loop.run_in_executor(
                None, lambda: ticker.fast_info
            )
            price = getattr(info, "last_price", None)
            if price is not None:
                return Decimal(str(price))
        except Exception as exc:
            logger.warning("Failed to fetch last price for %s: %s", clean, exc)

        # Fallback: grab last daily close
        try:
            bars = await self.fetch_bars(symbol, Timeframe.D1, limit=1)
            if bars:
                return bars[-1].close
        except Exception:
            pass

        return None

    async def fetch_universe(self) -> list[str]:
        """Load ticker symbols from the universe file.

        Handles both plain symbols (AAPL) and exchange-prefixed
        symbols (NASDAQ:AAPL). Returns cleaned symbols for yfinance.
        """
        if not self._universe_file.exists():
            raise FileNotFoundError(
                f"Universe file not found: {self._universe_file}. "
                f"Expected file at {self._universe_file.resolve()}."
            )

        symbols: list[str] = []
        with open(self._universe_file) as f:
            content = f.read()

        # Support both newline-separated and comma-separated formats
        raw_symbols = content.replace("\n", ",").split(",")
        for raw in raw_symbols:
            stripped = raw.strip()
            if stripped:
                symbols.append(self._clean_symbol(stripped).upper())

        return symbols
