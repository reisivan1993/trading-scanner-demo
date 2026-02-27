from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncGenerator

import pandas as pd

from packages.core.config import AppConfig
from packages.core.indicators import compute_all_indicators
from packages.core.models import (
    ChecklistItem,
    OHLCVBar,
    ScanResult,
    ScanRunMeta,
    ScoringBreakdown,
    SetupResult,
    Timeframe,
    TickerData,
)
from packages.core.resampling import (
    bars_to_dataframe,
    resample_1d_to_1w,
    resample_1m_to_15m,
    resample_1m_to_65m,
)
from packages.policy.engine import PolicyEngine
from packages.policy.schema import MergedPolicy
from packages.providers.base import BaseProvider
from packages.skills.checklist import evaluate_checklist
from packages.skills.patterns import detect_all_patterns
from packages.skills.risk_gate import run_risk_gate
from packages.skills.scoring import compute_score
from packages.skills.setup_generator import generate_setup
from packages.skills.support_resistance import detect_sr_zones
from packages.skills.vector_candles import detect_vector_candles

logger = logging.getLogger(__name__)


@dataclass
class UniverseItem:
    """Lightweight item for universe pre-filtering."""

    symbol: str
    price: float = 0.0
    avg_dollar_volume_20d: float = 0.0
    gap_pct: float | None = None


@dataclass
class TickerAnalysis:
    """Intermediate analysis result for a single ticker."""

    symbol: str
    ticker_data: TickerData
    df_1d: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_1w: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_65m: pd.DataFrame = field(default_factory=pd.DataFrame)
    sr_zones: list = field(default_factory=list)
    vector_candles: list = field(default_factory=list)
    patterns: list = field(default_factory=list)
    setup: Any = None
    score: Any = None
    passed_risk: bool = False


class ScanOrchestrator:
    """Wires the full scanning pipeline: provider -> resampling -> indicators ->
    skills -> policy hooks -> risk gate -> scoring -> ranking."""

    def __init__(
        self,
        config: AppConfig,
        provider: BaseProvider,
        policy: MergedPolicy,
        policy_engine: PolicyEngine | None = None,
        web_intel_fn: Any = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.policy = policy
        self.policy_engine = policy_engine or PolicyEngine()
        self.web_intel_fn = web_intel_fn

    async def run_single(self, symbol: str) -> ScanResult:
        """Scan a single ticker, bypassing universe loading and pre-filtering."""
        meta = ScanRunMeta(started_at=datetime.now())
        symbol = symbol.upper().strip()

        # Fetch current price and analysis in parallel
        current_price = await self.provider.fetch_last_trade_price(symbol)

        analyses = await self._analyze_tickers([symbol])
        analyses = self.policy_engine.post_features(analyses, self.policy)

        results: list[SetupResult] = []
        for analysis in analyses:
            setup_result = self._process_analysis(
                analysis, skip_risk_gate=True, override_price=current_price,
            )
            if setup_result is not None:
                setup_result.current_price = current_price
                results.append(setup_result)

        results = self.policy_engine.pre_score(results, self.policy)
        results = self.policy_engine.post_score(results, self.policy)

        results = self.policy_engine.pre_rank(results, self.policy)
        results.sort(key=lambda r: r.score.total, reverse=True)
        for i, r in enumerate(results):
            r.rank = i + 1
        results = self.policy_engine.post_rank(results, self.policy)

        meta.completed_at = datetime.now()
        meta.tickers_scanned = 1
        meta.setups_found = len(analyses)
        meta.setups_passed_risk = len(results)

        cash_is_position = len(results) == 0
        banner = "Cash is a position." if cash_is_position else ""

        return ScanResult(
            meta=meta,
            results=results,
            cash_is_position=cash_is_position,
            banner_message=banner,
        )

    async def run_strategy(self, strategy_name: str) -> ScanResult:
        """Execute a strategy-specific scan across the full universe."""
        from packages.skills.strategies import get_strategy

        strategy = get_strategy(strategy_name)
        meta = ScanRunMeta(started_at=datetime.now())

        symbols = await self.provider.fetch_universe()
        symbols = symbols[: self.config.universe.max_tickers_per_run]
        universe_items = await self._build_universe_items(symbols)
        filtered_items = self.policy_engine.pre_filter_universe(universe_items, self.policy)
        filtered_symbols = [item.symbol for item in filtered_items]
        logger.info("Strategy %s: %d symbols after pre-filter", strategy_name, len(filtered_symbols))

        analyses = await self._analyze_tickers(filtered_symbols)
        analyses = self.policy_engine.post_features(analyses, self.policy)

        screened: list[TickerAnalysis] = []
        for analysis in analyses:
            extra = strategy.extra_patterns(analysis.df_1d)
            analysis.patterns = analysis.patterns + extra
            if strategy.screen(
                analysis.df_1d, analysis.sr_zones,
                analysis.vector_candles, analysis.patterns,
            ):
                screened.append(analysis)

        logger.info("Strategy %s: %d passed screen", strategy_name, len(screened))

        results: list[SetupResult] = []
        for analysis in screened:
            setup_result = self._process_analysis_with_strategy(analysis, strategy)
            if setup_result is not None:
                results.append(setup_result)

        results = self.policy_engine.pre_score(results, self.policy)
        results = self.policy_engine.post_score(results, self.policy)
        results = self.policy_engine.pre_rank(results, self.policy)
        results.sort(key=lambda r: r.score.total, reverse=True)
        results = results[: strategy.result_limit]
        for i, r in enumerate(results):
            r.rank = i + 1
        results = self.policy_engine.post_rank(results, self.policy)

        meta.completed_at = datetime.now()
        meta.tickers_scanned = len(filtered_symbols)
        meta.setups_found = len(screened)
        meta.setups_passed_risk = len(results)

        cash_is_position = len(results) == 0
        banner = "Cash is a position." if cash_is_position else ""

        return ScanResult(
            meta=meta,
            results=results,
            cash_is_position=cash_is_position,
            banner_message=banner,
        )

    async def run(self) -> ScanResult:
        """Execute the full scanning pipeline in chunks, accumulating results."""
        meta = ScanRunMeta(started_at=datetime.now())
        chunk_size = self.config.universe.max_tickers_per_run

        # 1. Fetch full universe (no cap — chunk_size controls batch size)
        all_symbols = await self.provider.fetch_universe()
        logger.info("Loaded %d symbols total, chunk size=%d", len(all_symbols), chunk_size)

        # 2. Process in chunks of chunk_size, accumulating across all batches
        accumulated_results: list[SetupResult] = []
        total_filtered = 0
        total_analyses = 0

        for batch_start in range(0, len(all_symbols), chunk_size):
            chunk = all_symbols[batch_start : batch_start + chunk_size]
            batch_num = batch_start // chunk_size + 1
            total_batches = (len(all_symbols) + chunk_size - 1) // chunk_size
            logger.info("Chunk %d/%d: %s", batch_num, total_batches, chunk)

            universe_items = await self._build_universe_items(chunk)
            filtered_items = self.policy_engine.pre_filter_universe(universe_items, self.policy)
            filtered_symbols = [item.symbol for item in filtered_items]
            total_filtered += len(filtered_symbols)

            analyses = await self._analyze_tickers(filtered_symbols)
            analyses = self.policy_engine.post_features(analyses, self.policy)
            total_analyses += len(analyses)

            for analysis in analyses:
                setup_result = self._process_analysis(analysis)
                if setup_result is not None:
                    accumulated_results.append(setup_result)

        # 3. Apply policy hooks on combined results
        accumulated_results = self.policy_engine.pre_risk_gate(accumulated_results, self.policy)
        accumulated_results = self.policy_engine.post_risk_gate(accumulated_results, self.policy)

        accumulated_results = self.policy_engine.pre_score(accumulated_results, self.policy)
        accumulated_results = self.policy_engine.post_score(accumulated_results, self.policy)

        # 4. Rank combined results
        accumulated_results = self.policy_engine.pre_rank(accumulated_results, self.policy)
        accumulated_results.sort(key=lambda r: r.score.total, reverse=True)
        for i, r in enumerate(accumulated_results):
            r.rank = i + 1
        accumulated_results = self.policy_engine.post_rank(accumulated_results, self.policy)

        meta.completed_at = datetime.now()
        meta.tickers_scanned = total_filtered
        meta.setups_found = total_analyses
        meta.setups_passed_risk = len(accumulated_results)

        cash_is_position = len(accumulated_results) == 0
        banner = "Cash is a position." if cash_is_position else ""

        return ScanResult(
            meta=meta,
            results=accumulated_results,
            cash_is_position=cash_is_position,
            banner_message=banner,
        )

    async def run_streaming(self, chunk_size: int = 10) -> AsyncGenerator[ScanResult, None]:
        """Yield a partial ScanResult after each chunk of chunk_size tickers.

        Intermediate yields contain ranked results seen so far.
        The final yield applies the full policy hook pipeline.
        """
        meta = ScanRunMeta(started_at=datetime.now())
        all_symbols = await self.provider.fetch_universe()
        total = len(all_symbols)
        logger.info("Streaming scan: %d symbols in chunks of %d", total, chunk_size)

        accumulated: list[SetupResult] = []
        tickers_scanned = 0

        for batch_start in range(0, total, chunk_size):
            chunk = all_symbols[batch_start : batch_start + chunk_size]
            is_last = batch_start + chunk_size >= total

            universe_items = await self._build_universe_items(chunk)
            filtered = self.policy_engine.pre_filter_universe(universe_items, self.policy)
            filtered_symbols = [item.symbol for item in filtered]
            tickers_scanned += len(filtered_symbols)

            analyses = await self._analyze_tickers(filtered_symbols)
            analyses = self.policy_engine.post_features(analyses, self.policy)

            for analysis in analyses:
                result = self._process_analysis(analysis)
                if result is not None:
                    accumulated.append(result)

            if is_last:
                ranked: list[SetupResult] = self.policy_engine.pre_risk_gate(accumulated, self.policy)
                ranked = self.policy_engine.post_risk_gate(ranked, self.policy)
                ranked = self.policy_engine.pre_score(ranked, self.policy)
                ranked = self.policy_engine.post_score(ranked, self.policy)
                ranked = self.policy_engine.pre_rank(ranked, self.policy)
                ranked.sort(key=lambda r: r.score.total, reverse=True)
                for i, r in enumerate(ranked):
                    r.rank = i + 1
                ranked = self.policy_engine.post_rank(ranked, self.policy)
                meta.completed_at = datetime.now()
            else:
                ranked = sorted(accumulated, key=lambda r: r.score.total, reverse=True)
                for i, r in enumerate(ranked):
                    r.rank = i + 1

            yield ScanResult(
                meta=ScanRunMeta(
                    run_id=meta.run_id,
                    started_at=meta.started_at,
                    completed_at=meta.completed_at,
                    tickers_scanned=tickers_scanned,
                    setups_found=len(ranked),
                    setups_passed_risk=len(ranked),
                ),
                results=list(ranked),
                cash_is_position=not ranked,
                banner_message="Cash is a position." if not ranked else "",
            )

    async def _build_universe_items(self, symbols: list[str]) -> list[UniverseItem]:
        """Fetch daily bars and build universe items for pre-filtering."""
        items: list[UniverseItem] = []

        async def fetch_one(symbol: str) -> UniverseItem | None:
            try:
                bars = await self.provider.fetch_bars(symbol, Timeframe.D1, limit=30)
                if not bars:
                    return None
                df = bars_to_dataframe(bars)
                last_close = df["close"].iloc[-1]
                avg_vol = df["volume"].mean()
                avg_dollar_vol = avg_vol * df["close"].mean()

                gap_pct = None
                if len(df) >= 2:
                    prev_close = df["close"].iloc[-2]
                    if prev_close > 0:
                        gap_pct = ((df["open"].iloc[-1] - prev_close) / prev_close) * 100

                return UniverseItem(
                    symbol=symbol,
                    price=last_close,
                    avg_dollar_volume_20d=avg_dollar_vol,
                    gap_pct=gap_pct,
                )
            except Exception:
                logger.warning("Failed to fetch daily bars for %s", symbol, exc_info=True)
                return None

        # Fetch sequentially to respect API rate limits (free tier: 5 req/min)
        for symbol in symbols:
            try:
                item = await fetch_one(symbol)
                if item is not None:
                    items.append(item)
            except Exception:
                logger.warning("Failed to build universe item for %s", symbol, exc_info=True)

        return items

    async def _analyze_tickers(self, symbols: list[str]) -> list[TickerAnalysis]:
        """Fetch data, resample, compute indicators and skills for each ticker."""
        analyses: list[TickerAnalysis] = []

        async def analyze_one(symbol: str) -> TickerAnalysis | None:
            try:
                bars_1d = await self.provider.fetch_bars(symbol, Timeframe.D1, limit=250)
                bars_1m = await self.provider.fetch_bars(symbol, Timeframe.M1, limit=390)

                ticker_data = TickerData(symbol=symbol, bars_1d=bars_1d, bars_1m=bars_1m)

                # Resample
                if bars_1m:
                    ticker_data.bars_15m = resample_1m_to_15m(bars_1m)
                    ticker_data.bars_65m = resample_1m_to_65m(bars_1m)
                if bars_1d:
                    ticker_data.bars_1w = resample_1d_to_1w(bars_1d)

                # Compute indicators on daily
                df_1d = bars_to_dataframe(bars_1d) if bars_1d else pd.DataFrame()
                if not df_1d.empty:
                    df_1d = compute_all_indicators(df_1d)

                # Compute indicators on weekly
                df_1w = bars_to_dataframe(ticker_data.bars_1w) if ticker_data.bars_1w else pd.DataFrame()
                if not df_1w.empty:
                    df_1w = compute_all_indicators(df_1w)

                # Compute indicators on 65m
                df_65m = bars_to_dataframe(ticker_data.bars_65m) if ticker_data.bars_65m else pd.DataFrame()
                if not df_65m.empty:
                    df_65m = compute_all_indicators(df_65m)

                # Skills
                sr_zones = detect_sr_zones(df_1d) if not df_1d.empty else []
                vector_candles = detect_vector_candles(df_1d) if not df_1d.empty else []
                patterns = detect_all_patterns(df_1d) if not df_1d.empty else []

                return TickerAnalysis(
                    symbol=symbol,
                    ticker_data=ticker_data,
                    df_1d=df_1d,
                    df_1w=df_1w,
                    df_65m=df_65m,
                    sr_zones=sr_zones,
                    vector_candles=vector_candles,
                    patterns=patterns,
                )
            except Exception:
                logger.warning("Failed to analyze %s", symbol, exc_info=True)
                return None

        # Fetch sequentially to respect API rate limits (free tier: 5 req/min)
        for symbol in symbols:
            try:
                result = await analyze_one(symbol)
                if result is not None:
                    analyses.append(result)
            except Exception:
                logger.warning("Failed to analyze %s", symbol, exc_info=True)

        return analyses

    def _process_analysis(
        self,
        analysis: TickerAnalysis,
        skip_risk_gate: bool = False,
        override_price: Decimal | None = None,
    ) -> SetupResult | None:
        """Generate setup, run risk gate, score, and return result if passed."""
        df = analysis.df_1d
        if df.empty or len(df) < 2:
            return None

        last_close = float(override_price) if override_price else float(df["close"].iloc[-1])
        atr_val = float(df["atr_14"].iloc[-1]) if "atr_14" in df.columns else 1.0

        # Determine direction from patterns or momentum
        direction = "long"
        if analysis.patterns:
            direction = analysis.patterns[0].direction
        elif "rsi_14" in df.columns and df["rsi_14"].iloc[-1] < 40:
            direction = "short"

        # Generate setup
        setup = generate_setup(
            symbol=analysis.symbol,
            direction=direction,
            entry_price=last_close,
            atr=atr_val,
            position_size_usd=self.config.position.size_usd,
            sr_zones=analysis.sr_zones,
        )

        # Risk gate
        avg_dollar_volume = float(df["close"].mean() * df["volume"].mean())
        rvol_val = float(df["rvol_20"].iloc[-1]) if "rvol_20" in df.columns else None

        gate_result = run_risk_gate(
            setup,
            min_rr=self.policy.risk_gate.min_rr,
            max_stop_pct=self.policy.risk_gate.max_stop_pct_of_price,
            avg_dollar_volume=avg_dollar_volume,
            min_dollar_volume=self.policy.universe.min_avg_dollar_volume_20d,
            allow_penny=self.config.risk_defaults.allow_penny,
            min_price=self.policy.universe.min_price,
            max_stop_dollars=(
                self.policy.risk_gate_extensions.max_stop_dollars
            ),
            rvol=rvol_val,
            min_rvol_short=self.policy.short_rules.min_rvol if direction == "short" else None,
        )

        if not gate_result.passed and not skip_risk_gate:
            logger.debug("Risk gate rejected %s: %s", analysis.symbol, gate_result.reason)
            return None

        # Check EMA alignment
        ema_alignment = False
        if all(col in df.columns for col in ["ema_9", "ema_20", "ema_50"]):
            last = df.iloc[-1]
            if direction == "long":
                ema_alignment = last["ema_9"] > last["ema_20"] > last["ema_50"]
            else:
                ema_alignment = last["ema_9"] < last["ema_20"] < last["ema_50"]

        rsi_val = float(df["rsi_14"].iloc[-1]) if "rsi_14" in df.columns else None
        stop_distance_atr = abs(float(setup.entry - setup.stop)) / atr_val if atr_val > 0 else None

        # Web intelligence modifier
        web_modifier = 0.0
        if self.web_intel_fn is not None:
            try:
                web_modifier = self.web_intel_fn(analysis.symbol)
            except Exception:
                logger.warning("Web intel failed for %s", analysis.symbol, exc_info=True)

        # Score
        score = compute_score(
            sr_zones=analysis.sr_zones,
            vector_candles=analysis.vector_candles,
            patterns=analysis.patterns,
            rr_ratio=setup.rr_ratio,
            stop_distance_atr=stop_distance_atr,
            rsi_val=rsi_val,
            ema_alignment=ema_alignment,
            rvol_val=rvol_val,
            df=df,
            web_intel_modifier=web_modifier,
        )

        basis = self._build_basis(
            direction=direction,
            patterns=analysis.patterns,
            sr_zones=analysis.sr_zones,
            vector_candles=analysis.vector_candles,
            ema_alignment=ema_alignment,
            rsi_val=rsi_val,
            rvol_val=rvol_val,
            rr_ratio=setup.rr_ratio,
        )

        checklist = evaluate_checklist(
            df_1d=df,
            df_1w=analysis.df_1w,
            sr_zones=analysis.sr_zones,
            direction=direction,
            entry_price=last_close,
        )

        return SetupResult(
            symbol=analysis.symbol,
            direction=direction,
            setup=setup,
            score=score,
            patterns=analysis.patterns,
            sr_zones=analysis.sr_zones,
            vector_candles=analysis.vector_candles,
            checklist=checklist,
            basis=basis,
        )

    @staticmethod
    def _build_basis(
        direction: str,
        patterns: list,
        sr_zones: list,
        vector_candles: list,
        ema_alignment: bool,
        rsi_val: float | None,
        rvol_val: float | None,
        rr_ratio: float,
    ) -> str:
        """Build a short human-readable rationale for the setup."""
        parts: list[str] = []

        if patterns:
            names = [p.name for p in patterns[:2]]
            parts.append(", ".join(names))

        if ema_alignment:
            label = "bullish" if direction == "long" else "bearish"
            parts.append(f"EMA alignment ({label})")

        if rsi_val is not None:
            if direction == "long" and rsi_val > 50:
                parts.append(f"RSI {rsi_val:.0f} (momentum)")
            elif direction == "short" and rsi_val < 50:
                parts.append(f"RSI {rsi_val:.0f} (weak)")
            else:
                parts.append(f"RSI {rsi_val:.0f}")

        if rvol_val is not None and rvol_val > 1.2:
            parts.append(f"RVOL {rvol_val:.1f}x")

        sr_support = [z for z in sr_zones if z.zone_type == "support"]
        sr_resist = [z for z in sr_zones if z.zone_type == "resistance"]
        if direction == "long" and sr_support:
            parts.append(f"near support ${sr_support[0].price:.2f}")
        elif direction == "short" and sr_resist:
            parts.append(f"near resistance ${sr_resist[0].price:.2f}")

        if vector_candles:
            tags = {vc.tag for vc in vector_candles[:3]}
            parts.append(f"vector candle: {', '.join(tags)}")

        parts.append(f"R:R {rr_ratio:.1f}")

        return ". ".join(parts) + "." if parts else "No specific catalyst."

    def _process_analysis_with_strategy(
        self, analysis: TickerAnalysis, strategy: Any,
    ) -> SetupResult | None:
        """Like _process_analysis but uses strategy-specific scoring."""
        df = analysis.df_1d
        if df.empty or len(df) < 2:
            return None

        last_close = float(df["close"].iloc[-1])
        atr_val = float(df["atr_14"].iloc[-1]) if "atr_14" in df.columns else 1.0

        direction = "long"
        if analysis.patterns:
            direction = analysis.patterns[0].direction
        elif "rsi_14" in df.columns and df["rsi_14"].iloc[-1] < 40:
            direction = "short"

        setup = generate_setup(
            symbol=analysis.symbol,
            direction=direction,
            entry_price=last_close,
            atr=atr_val,
            position_size_usd=self.config.position.size_usd,
            sr_zones=analysis.sr_zones,
        )

        ema_alignment = False
        if all(col in df.columns for col in ["ema_9", "ema_20", "ema_50"]):
            last = df.iloc[-1]
            if direction == "long":
                ema_alignment = last["ema_9"] > last["ema_20"] > last["ema_50"]
            else:
                ema_alignment = last["ema_9"] < last["ema_20"] < last["ema_50"]

        rsi_val = float(df["rsi_14"].iloc[-1]) if "rsi_14" in df.columns else None
        rvol_val = float(df["rvol_20"].iloc[-1]) if "rvol_20" in df.columns else None
        stop_distance_atr = abs(float(setup.entry - setup.stop)) / atr_val if atr_val > 0 else None

        score = strategy.score_fn(
            sr_zones=analysis.sr_zones,
            vector_candles=analysis.vector_candles,
            patterns=analysis.patterns,
            rr_ratio=setup.rr_ratio,
            stop_distance_atr=stop_distance_atr,
            rsi_val=rsi_val,
            ema_alignment=ema_alignment,
            rvol_val=rvol_val,
            df=df,
            web_intel_modifier=0.0,
        )

        basis = self._build_basis(
            direction=direction,
            patterns=analysis.patterns,
            sr_zones=analysis.sr_zones,
            vector_candles=analysis.vector_candles,
            ema_alignment=ema_alignment,
            rsi_val=rsi_val,
            rvol_val=rvol_val,
            rr_ratio=setup.rr_ratio,
        )

        checklist = evaluate_checklist(
            df_1d=df,
            df_1w=analysis.df_1w,
            sr_zones=analysis.sr_zones,
            direction=direction,
            entry_price=last_close,
        )

        return SetupResult(
            symbol=analysis.symbol,
            direction=direction,
            setup=setup,
            score=score,
            patterns=analysis.patterns,
            sr_zones=analysis.sr_zones,
            vector_candles=analysis.vector_candles,
            checklist=checklist,
            basis=basis,
        )
