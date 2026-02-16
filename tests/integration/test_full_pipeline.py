from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.config import AppConfig, PolicyPathsConfig, PositionConfig, ProviderConfig, UniverseConfig
from packages.core.orchestrator import ScanOrchestrator
from packages.policy.engine import PolicyEngine
from packages.policy.loader import load_policies
from packages.providers.csv_provider import CsvProvider
from packages.skills.reporting import generate_csv_report, generate_markdown_report
from packages.skills.tradingview_export import generate_watchlist_csv


@pytest.fixture
def full_config() -> AppConfig:
    return AppConfig(
        provider=ProviderConfig(name="csv"),
        universe=UniverseConfig(source_file="data/universe/spy.txt", max_tickers_per_run=5),
        position=PositionConfig(size_usd=10000),
        policy=PolicyPathsConfig(enable_advanced=True),
    )


@pytest.fixture
def csv_provider() -> CsvProvider:
    return CsvProvider(
        data_dir=Path("data/sample"),
        universe_file=Path("data/universe/spy.txt"),
    )


async def test_full_pipeline_with_all_policy_layers(
    full_config: AppConfig,
    csv_provider: CsvProvider,
) -> None:
    """End-to-end test with all three policy layers merged."""
    policy = load_policies(full_config)
    engine = PolicyEngine()

    orchestrator = ScanOrchestrator(
        config=full_config,
        provider=csv_provider,
        policy=policy,
        policy_engine=engine,
    )

    result = await orchestrator.run()

    assert result.meta.run_id
    assert result.meta.completed_at is not None
    assert isinstance(result.results, list)

    # Verify policy was applied
    assert policy.risk_gate.min_rr == 2.5  # from user_overrides
    assert policy.risk_gate_extensions.max_stop_dollars == 250.0  # from advanced


async def test_full_pipeline_report_generation(
    full_config: AppConfig,
    csv_provider: CsvProvider,
) -> None:
    """Pipeline output can be converted to all report formats."""
    policy = load_policies(full_config)
    orchestrator = ScanOrchestrator(
        config=full_config,
        provider=csv_provider,
        policy=policy,
    )

    result = await orchestrator.run()

    md_report = generate_markdown_report(result, language="he")
    assert "סורק" in md_report or "Cold" in md_report

    csv_report = generate_csv_report(result)
    assert "Rank" in csv_report

    tv_export = generate_watchlist_csv(result)
    assert "symbol" in tv_export


async def test_full_pipeline_ranking_order(
    full_config: AppConfig,
    csv_provider: CsvProvider,
) -> None:
    """Results should be ranked by score descending."""
    policy = load_policies(full_config)
    orchestrator = ScanOrchestrator(
        config=full_config,
        provider=csv_provider,
        policy=policy,
    )

    result = await orchestrator.run()

    if len(result.results) > 1:
        scores = [r.score.total for r in result.results]
        assert scores == sorted(scores, reverse=True)
        ranks = [r.rank for r in result.results]
        assert ranks == list(range(1, len(ranks) + 1))
