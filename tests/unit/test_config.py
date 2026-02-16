from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from packages.core.config import AppConfig, load_config


class TestLoadConfig:
    def test_load_config_from_file(self, tmp_path: Path) -> None:
        cfg_data = {
            "environment": "test",
            "timezone": {"market": "America/New_York", "local": "Asia/Jerusalem"},
            "provider": {"name": "csv", "max_retries": 1},
            "universe": {"source_file": "./data/universe/spy.txt"},
        }
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump(cfg_data))

        config = load_config(cfg_file)

        assert config.environment == "test"
        assert config.provider.name == "csv"
        assert config.provider.max_retries == 1
        assert config.timezone.market == "America/New_York"

    def test_load_config_defaults(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"environment": "dev"}))

        config = load_config(cfg_file)

        assert config.provider.name == "polygon"
        assert config.risk_defaults.min_rr == 2.0
        assert config.position.size_usd == 10000
        assert config.logging.structured is True

    def test_load_config_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yml")

    def test_load_config_empty_file_raises(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text("")

        with pytest.raises(ValueError, match="empty"):
            load_config(cfg_file)

    def test_load_real_config(self) -> None:
        config = load_config("config.yml")

        assert config.environment == "production"
        assert config.provider.name == "polygon"
        assert config.schedule.only_us_trading_days is True
        assert config.output.language == "he"


class TestAppConfigModel:
    def test_model_with_all_defaults(self) -> None:
        config = AppConfig()

        assert config.environment == "production"
        assert config.timezone.market == "America/New_York"
        assert config.risk_defaults.allow_penny is False
