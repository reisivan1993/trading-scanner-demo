from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from packages.core.config import AppConfig, ProviderConfig, UniverseConfig
from packages.core.models import OHLCVBar, Timeframe
from packages.providers.csv_provider import CsvProvider
from packages.providers.factory import get_provider

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample"
UNIVERSE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "universe" / "spy.txt"


@pytest.fixture
def csv_provider() -> CsvProvider:
    return CsvProvider(data_dir=SAMPLE_DIR, universe_file=UNIVERSE_FILE)


async def test_csv_provider_fetch_bars_1d(csv_provider: CsvProvider) -> None:
    """Load AAPL_1d.csv and verify correct count and types."""
    bars = await csv_provider.fetch_bars("AAPL", Timeframe.D1)

    assert len(bars) == 30
    assert all(isinstance(b, OHLCVBar) for b in bars)
    assert all(b.timeframe == Timeframe.D1 for b in bars)
    assert all(isinstance(b.open, Decimal) for b in bars)
    assert all(isinstance(b.close, Decimal) for b in bars)
    assert all(isinstance(b.volume, int) for b in bars)

    # Verify bars are sorted by timestamp ascending
    for i in range(len(bars) - 1):
        assert bars[i].timestamp <= bars[i + 1].timestamp

    # Spot-check first bar values
    first = bars[0]
    assert first.open == Decimal("171.21")
    assert first.high == Decimal("172.50")
    assert first.low == Decimal("170.12")
    assert first.close == Decimal("171.48")
    assert first.volume == 45123400


async def test_csv_provider_fetch_bars_1m(csv_provider: CsvProvider) -> None:
    """Load AAPL_1m.csv and verify correct count and types."""
    bars = await csv_provider.fetch_bars("AAPL", Timeframe.M1)

    assert len(bars) == 50
    assert all(isinstance(b, OHLCVBar) for b in bars)
    assert all(b.timeframe == Timeframe.M1 for b in bars)

    # Verify bars are sorted by timestamp ascending
    for i in range(len(bars) - 1):
        assert bars[i].timestamp <= bars[i + 1].timestamp

    # Spot-check first bar
    first = bars[0]
    assert first.open == Decimal("184.30")
    assert first.close == Decimal("184.45")


async def test_csv_provider_fetch_universe(csv_provider: CsvProvider) -> None:
    """Read spy.txt and verify it returns a list of symbols."""
    symbols = await csv_provider.fetch_universe()

    assert isinstance(symbols, list)
    assert len(symbols) > 0
    assert all(isinstance(s, str) for s in symbols)
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    # Verify all symbols are uppercase and stripped
    assert all(s == s.strip().upper() for s in symbols)


async def test_csv_provider_missing_file_raises() -> None:
    """FileNotFoundError is raised when CSV file does not exist."""
    provider = CsvProvider(
        data_dir=Path("/nonexistent/path"),
        universe_file=UNIVERSE_FILE,
    )
    with pytest.raises(FileNotFoundError, match="CSV data file not found"):
        await provider.fetch_bars("AAPL", Timeframe.D1)


async def test_csv_provider_missing_universe_raises() -> None:
    """FileNotFoundError is raised when universe file does not exist."""
    provider = CsvProvider(
        data_dir=SAMPLE_DIR,
        universe_file=Path("/nonexistent/spy.txt"),
    )
    with pytest.raises(FileNotFoundError, match="Universe file not found"):
        await provider.fetch_universe()


def test_factory_csv() -> None:
    """get_provider returns CsvProvider when config.provider.name is 'csv'."""
    config = AppConfig(
        provider=ProviderConfig(name="csv"),
        universe=UniverseConfig(source_file=str(SAMPLE_DIR / "spy.txt")),
    )
    provider = get_provider(config)
    assert isinstance(provider, CsvProvider)


def test_factory_unknown_raises() -> None:
    """ValueError is raised for an unknown provider name."""
    config = AppConfig(
        provider=ProviderConfig(name="polygon"),  # type: ignore[arg-type]
        universe=UniverseConfig(source_file="./data/universe/spy.txt"),
    )
    # We need to pass an invalid name, but ProviderConfig validates it.
    # So we override after creation.
    config.provider.name = "unknown"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Unknown provider name"):
        get_provider(config)
