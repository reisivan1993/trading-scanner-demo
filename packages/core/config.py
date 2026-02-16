from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class TimezoneConfig(BaseModel):
    market: str = "America/New_York"
    local: str = "Asia/Jerusalem"


class ProviderConfig(BaseModel):
    name: Literal["polygon", "alpaca", "csv"] = "polygon"
    max_retries: int = 3
    backoff_seconds: float = 2.0
    rate_limit_per_minute: int = 120


class UniverseConfig(BaseModel):
    source_file: str = "./data/universe/spy.txt"
    max_tickers_per_run: int = 600


class ScheduleConfig(BaseModel):
    mode: str = "market_close_plus"
    minutes_after_close: int = 10
    fixed_time_israel: str = "19:30"
    only_us_trading_days: bool = True
    use_market_calendar: bool = True


class PositionConfig(BaseModel):
    size_usd: int = 10000


class RiskDefaultsConfig(BaseModel):
    min_rr: float = 2.0
    target_profit_min: float = 500.0
    target_profit_max: float = 1000.0
    allow_penny: bool = False


class PolicyPathsConfig(BaseModel):
    default_file: str = "./policies/default.yml"
    user_override_file: str = "./policies/user_overrides.yml"
    advanced_override_file: str = "./policies/user_overrides_advanced.yml"
    enable_advanced: bool = True


class WebIntelligenceConfig(BaseModel):
    enabled: bool = True
    provider: str = "quercle"
    lookback_days: int = 3
    earnings_lookahead_days: int = 7


class OutputConfig(BaseModel):
    base_path: str = "./data/output"
    language: Literal["en", "he"] = "en"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    structured: bool = True
    log_rule_decisions: bool = True


class AppConfig(BaseModel):
    environment: str = "production"
    timezone: TimezoneConfig = Field(default_factory=TimezoneConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    position: PositionConfig = Field(default_factory=PositionConfig)
    risk_defaults: RiskDefaultsConfig = Field(default_factory=RiskDefaultsConfig)
    policy: PolicyPathsConfig = Field(default_factory=PolicyPathsConfig)
    web_intelligence: WebIntelligenceConfig = Field(default_factory=WebIntelligenceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(path: str | Path = "config.yml") -> AppConfig:
    """Load application config from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Config file is empty: {config_path}")

    return AppConfig.model_validate(raw)
