from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from packages.core.config import AppConfig, ProviderConfig, UniverseConfig, PositionConfig
from packages.core.orchestrator import ScanOrchestrator
from packages.policy.engine import PolicyEngine
from packages.policy.schema import MergedPolicy
from packages.providers.csv_provider import CsvProvider


@pytest.fixture
def csv_provider() -> CsvProvider:
    return CsvProvider(
        data_dir=Path("data/sample"),
        universe_file=Path("data/universe/spy.txt"),
    )


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(
        provider=ProviderConfig(name="csv"),
        universe=UniverseConfig(source_file="data/universe/spy.txt", max_tickers_per_run=5),
        position=PositionConfig(size_usd=10000),
    )


@pytest.fixture
def policy() -> MergedPolicy:
    return MergedPolicy()


async def test_pipeline_end_to_end(
    csv_provider: CsvProvider,
    config: AppConfig,
    policy: MergedPolicy,
) -> None:
    """Full pipeline with CsvProvider - should run without errors."""
    orchestrator = ScanOrchestrator(
        config=config,
        provider=csv_provider,
        policy=policy,
        policy_engine=PolicyEngine(),
    )
    result = await orchestrator.run()

    assert result.meta.run_id
    assert result.meta.completed_at is not None
    # With only AAPL sample data, most tickers will fail to load
    # but the pipeline should still complete gracefully
    assert isinstance(result.results, list)


async def test_pipeline_cash_is_position(
    config: AppConfig,
    policy: MergedPolicy,
) -> None:
    """Pipeline with empty data produces 'cash is a position'."""
    empty_provider = CsvProvider(
        data_dir=Path("data/nonexistent"),
        universe_file=Path("data/universe/spy.txt"),
    )
    orchestrator = ScanOrchestrator(
        config=config,
        provider=empty_provider,
        policy=policy,
        policy_engine=PolicyEngine(),
    )
    result = await orchestrator.run()

    assert result.cash_is_position is True
    assert "Cash" in result.banner_message
