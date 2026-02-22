from __future__ import annotations

from pathlib import Path

from packages.core.config import AppConfig
from packages.providers.alpaca_provider import AlpacaProvider
from packages.providers.base import BaseProvider
from packages.providers.csv_provider import CsvProvider
from packages.providers.polygon_provider import PolygonProvider
from packages.providers.yfinance_provider import YFinanceProvider


def get_provider(config: AppConfig) -> BaseProvider:
    """Create and return a data provider based on configuration.

    Args:
        config: Application configuration containing provider settings.

    Returns:
        An instance of the appropriate BaseProvider subclass.

    Raises:
        ValueError: If the configured provider name is not recognized.
    """
    universe_file = Path(config.universe.source_file)
    name = config.provider.name

    if name == "csv":
        data_dir = Path("data/sample")
        return CsvProvider(data_dir=data_dir, universe_file=universe_file)

    if name == "polygon":
        return PolygonProvider(
            universe_file=universe_file,
            max_retries=config.provider.max_retries,
            backoff_seconds=config.provider.backoff_seconds,
            rate_limit_per_minute=config.provider.rate_limit_per_minute,
        )

    if name == "alpaca":
        return AlpacaProvider()

    if name == "yfinance":
        return YFinanceProvider(
            universe_file=universe_file,
            rate_limit_per_minute=config.provider.rate_limit_per_minute,
        )

    raise ValueError(
        f"Unknown provider name: {name!r}. "
        f"Supported providers: 'csv', 'polygon', 'alpaca', 'yfinance'."
    )
