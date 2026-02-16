from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_config, get_data_provider, get_policy, get_policy_engine
from apps.api.routes import router
from packages.core.config import AppConfig, PositionConfig, ProviderConfig, UniverseConfig
from packages.policy.engine import PolicyEngine
from packages.policy.schema import MergedPolicy
from packages.providers.csv_provider import CsvProvider


def _test_config() -> AppConfig:
    return AppConfig(
        provider=ProviderConfig(name="csv"),
        universe=UniverseConfig(source_file="data/universe/spy.txt", max_tickers_per_run=3),
        position=PositionConfig(size_usd=10000),
    )


def _test_provider() -> CsvProvider:
    return CsvProvider(
        data_dir=Path("data/sample"),
        universe_file=Path("data/universe/spy.txt"),
    )


@asynccontextmanager
async def _noop_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


@pytest.fixture
def client() -> TestClient:
    test_app = FastAPI(lifespan=_noop_lifespan)
    test_app.include_router(router)
    test_app.dependency_overrides[get_config] = _test_config
    test_app.dependency_overrides[get_data_provider] = _test_provider
    test_app.dependency_overrides[get_policy] = lambda: MergedPolicy()
    test_app.dependency_overrides[get_policy_engine] = lambda: PolicyEngine()
    return TestClient(test_app)


class TestHealthEndpoint:
    def test_health(self) -> None:
        # health is on the main app, test it separately
        from apps.api.main import app

        with TestClient(app) as c:
            resp = c.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"


class TestScanEndpoints:
    def test_scan_run(self, client: TestClient) -> None:
        resp = client.post("/scan/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert "tickers_scanned" in data

    def test_scan_latest_after_run(self, client: TestClient) -> None:
        client.post("/scan/run")
        resp = client.get("/scan/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "meta" in data
        assert "results" in data

    def test_scan_latest_no_data(self, client: TestClient) -> None:
        from apps.api import routes

        routes._scan_results.clear()
        routes._latest_run_id = None

        resp = client.get("/scan/latest")
        assert resp.status_code == 404

    def test_export_tradingview(self, client: TestClient) -> None:
        client.post("/scan/run")
        resp = client.get("/export/tradingview")
        assert resp.status_code == 200
        data = resp.json()
        assert "watchlist_csv" in data
        assert "watchlist_comma" in data
