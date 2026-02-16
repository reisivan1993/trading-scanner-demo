from __future__ import annotations

from pydantic import BaseModel, Field


class OutputPolicy(BaseModel):
    language: str = "en"
    report_verbosity: str = "medium"
    include_momentum_only_list: bool = True
    tradingview_export: bool = True


class ExcludeGapDays(BaseModel):
    enabled: bool = False
    gap_pct_threshold: float = 5.0


class UniversePolicy(BaseModel):
    min_price: float = 2.0
    min_avg_dollar_volume_20d: float = 20_000_000
    exclude_gap_days: ExcludeGapDays = Field(default_factory=ExcludeGapDays)


class RiskGatePolicy(BaseModel):
    min_rr: float = 2.0
    max_stop_pct_of_price: float | None = None
    target_profit_min: float = 500.0
    target_profit_max: float = 1000.0


class RiskGateExtensions(BaseModel):
    max_stop_dollars: float | None = None
    require_stop_near_structure: bool = False


class MarketStructureFilters(BaseModel):
    wick_ratio_max: float | None = None


class ShortRules(BaseModel):
    require_breakdown_confirmation: bool = False
    min_breakdown_atr: float | None = None
    min_rvol: float | None = None


class LongRules(BaseModel):
    max_distance_from_support_atr: float | None = None


class OutputExtensions(BaseModel):
    momentum_only_min_score: int | None = None


class MergedPolicy(BaseModel):
    version: int = 1
    output: OutputPolicy = Field(default_factory=OutputPolicy)
    universe: UniversePolicy = Field(default_factory=UniversePolicy)
    risk_gate: RiskGatePolicy = Field(default_factory=RiskGatePolicy)
    risk_gate_extensions: RiskGateExtensions = Field(default_factory=RiskGateExtensions)
    market_structure_filters: MarketStructureFilters = Field(default_factory=MarketStructureFilters)
    short_rules: ShortRules = Field(default_factory=ShortRules)
    long_rules: LongRules = Field(default_factory=LongRules)
    output_extensions: OutputExtensions = Field(default_factory=OutputExtensions)
