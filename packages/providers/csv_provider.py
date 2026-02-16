from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.core.models import OHLCVBar, Timeframe
from packages.providers.base import BaseProvider


class CsvProvider(BaseProvider):
    """Market data provider that reads from local CSV files.

    CSV files must have columns: timestamp, open, high, low, close, volume.
    Files are located at ``{data_dir}/{symbol}_{timeframe.value}.csv``.
    """

    def __init__(self, data_dir: Path, universe_file: Path) -> None:
        self._data_dir = data_dir
        self._universe_file = universe_file

    async def fetch_bars(
        self, symbol: str, timeframe: Timeframe, limit: int = 390
    ) -> list[OHLCVBar]:
        """Read OHLCV bars from a CSV file on disk.

        Args:
            symbol: Ticker symbol (e.g. "AAPL").
            timeframe: Bar timeframe (e.g. Timeframe.D1).
            limit: Maximum number of bars to return.

        Returns:
            List of OHLCVBar objects sorted by timestamp ascending.

        Raises:
            FileNotFoundError: If the CSV file does not exist.
        """
        filename = f"{symbol}_{timeframe.value}.csv"
        filepath = self._data_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(
                f"CSV data file not found: {filepath}. "
                f"Expected file at {filepath.resolve()} for symbol={symbol}, "
                f"timeframe={timeframe.value}."
            )

        bars: list[OHLCVBar] = []
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                bar = OHLCVBar(
                    timestamp=ts,
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=int(row["volume"]),
                    timeframe=timeframe,
                )
                bars.append(bar)

        bars.sort(key=lambda b: b.timestamp)
        return bars[:limit]

    async def fetch_universe(self) -> list[str]:
        """Read ticker symbols from the universe file, one per line.

        Returns:
            List of uppercase ticker symbols.

        Raises:
            FileNotFoundError: If the universe file does not exist.
        """
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
