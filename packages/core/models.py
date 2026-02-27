from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Timeframe(str, Enum):
    M1 = "1m"
    M15 = "15m"
    M65 = "65m"
    D1 = "1d"
    W1 = "1w"


class OHLCVBar(BaseModel, frozen=True):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    timeframe: Timeframe


class TickerData(BaseModel):
    symbol: str
    bars_1m: list[OHLCVBar] = Field(default_factory=list)
    bars_15m: list[OHLCVBar] = Field(default_factory=list)
    bars_65m: list[OHLCVBar] = Field(default_factory=list)
    bars_1d: list[OHLCVBar] = Field(default_factory=list)
    bars_1w: list[OHLCVBar] = Field(default_factory=list)


class SRZone(BaseModel, frozen=True):
    price: Decimal
    zone_type: Literal["support", "resistance"]
    touches: int = 0
    strength: float = 0.0


class VectorCandle(BaseModel, frozen=True):
    bar: OHLCVBar
    tag: Literal["follow-through", "absorption", "rejection"]
    atr_multiple: float
    volume_multiple: float


class PatternMatch(BaseModel, frozen=True):
    name: str
    direction: Literal["long", "short"]
    confidence: float = Field(ge=0.0, le=1.0)
    description: str = ""


class TradeSetup(BaseModel, frozen=True):
    symbol: str
    direction: Literal["long", "short"]
    entry: Decimal
    stop: Decimal
    target_1: Decimal
    target_2: Decimal | None = None
    rr_ratio: float
    shares: int
    dollar_risk: Decimal
    dollar_pnl_t1: Decimal
    dollar_pnl_t2: Decimal | None = None


class ScoringBreakdown(BaseModel, frozen=True):
    confluence: float = 0.0
    invalidation: float = 0.0
    rr: float = 0.0
    momentum: float = 0.0
    volume: float = 0.0
    pattern: float = 0.0
    cleanliness: float = 0.0
    web_intel_modifier: float = 0.0
    total: float = 0.0


class ChecklistItem(BaseModel, frozen=True):
    criterion: str
    passed: bool
    value: str | None = None
    notes: str = ""


class SetupResult(BaseModel):
    symbol: str
    direction: Literal["long", "short"]
    setup: TradeSetup
    score: ScoringBreakdown
    patterns: list[PatternMatch] = Field(default_factory=list)
    sr_zones: list[SRZone] = Field(default_factory=list)
    vector_candles: list[VectorCandle] = Field(default_factory=list)
    web_intel_notes: list[str] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    rank: int = 0
    current_price: Decimal | None = None
    basis: str = ""


class ScanRunMeta(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    tickers_scanned: int = 0
    setups_found: int = 0
    setups_passed_risk: int = 0
    policy_version: int = 1
    config_snapshot: dict = Field(default_factory=dict)  # type: ignore[type-arg]


class ScanResult(BaseModel):
    meta: ScanRunMeta
    results: list[SetupResult] = Field(default_factory=list)
    cash_is_position: bool = False
    banner_message: str = ""


class VolumeConditionTag(StrEnum):
    HEALTHY_MOVE = "healthy_move"
    EFFORT_NO_RESULT = "effort_no_result"
    NO_SUPPLY = "no_supply"
    NO_DEMAND = "no_demand"
    NEUTRAL = "neutral"


class VSAPatternTag(StrEnum):
    STOPPING_VOLUME = "stopping_volume"
    BUYING_CLIMAX = "buying_climax"
    NO_SUPPLY_TEST = "no_supply_test"
    NO_DEMAND_TEST = "no_demand_test"


class BarVolumeCondition(BaseModel, frozen=True):
    bar_index: int
    vol_rel: float
    spread_rel: float
    close_pos: float
    condition: VolumeConditionTag


class VSASignal(BaseModel, frozen=True):
    pattern: VSAPatternTag
    bar_index: int
    direction: Literal["bullish", "bearish"]
    confidence: float = Field(ge=0.0, le=1.0)
    description: str = ""


class VolumeDivergence(BaseModel, frozen=True):
    divergence_type: Literal["bullish", "bearish"]
    lookback_bars: int
    confidence: float = Field(ge=0.0, le=1.0)
    description: str = ""


class BreakoutValidity(BaseModel, frozen=True):
    level: Decimal
    direction: Literal["long", "short"]
    is_valid: bool
    vol_rel: float
    spread_rel: float
    reason: str


class VolumeAnalysisResult(BaseModel, frozen=True):
    conditions: list[BarVolumeCondition]
    vsa_signals: list[VSASignal]
    divergences: list[VolumeDivergence]
    breakout_signals: list[BreakoutValidity]
    bias: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str]
