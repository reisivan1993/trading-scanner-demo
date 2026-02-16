from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from packages.core.models import PatternMatch, SRZone, VectorCandle
from packages.skills.scoring import (
    WEIGHTS,
    compute_score,
    score_confluence,
    score_momentum,
    score_pattern,
    score_rr,
    score_volume,
)


class TestScoreRR:
    def test_high_rr(self) -> None:
        assert score_rr(5.0) == 100.0

    def test_low_rr(self) -> None:
        assert score_rr(1.0) == 20.0

    def test_capped_at_100(self) -> None:
        assert score_rr(10.0) == 100.0


class TestScoreMomentum:
    def test_bullish_rsi(self) -> None:
        result = score_momentum(rsi=60.0, ema_alignment=True)
        assert result == 100.0

    def test_neutral(self) -> None:
        result = score_momentum()
        assert result == 50.0


class TestScoreVolume:
    def test_high_rvol(self) -> None:
        assert score_volume(2.5) == 100.0

    def test_low_rvol(self) -> None:
        assert score_volume(0.5) < 50.0

    def test_none_rvol(self) -> None:
        assert score_volume(None) == 50.0


class TestScorePattern:
    def test_with_patterns(self) -> None:
        patterns = [
            PatternMatch(name="breakout", direction="long", confidence=0.8),
        ]
        assert score_pattern(patterns) == 80.0

    def test_no_patterns(self) -> None:
        assert score_pattern([]) == 0.0


class TestScoreConfluence:
    def test_many_signals(self) -> None:
        from decimal import Decimal
        from packages.core.models import OHLCVBar, Timeframe
        from datetime import datetime

        zones = [SRZone(price=Decimal("170"), zone_type="support", touches=3, strength=0.8)]
        patterns = [PatternMatch(name="flag", direction="long", confidence=0.7)]
        result = score_confluence(zones, [], patterns)
        assert result > 0


class TestComputeScore:
    def test_weights_sum_to_one(self) -> None:
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_full_scoring(self) -> None:
        result = compute_score(
            rr_ratio=3.0,
            rsi_val=60.0,
            rvol_val=1.8,
            ema_alignment=True,
        )
        assert result.total > 0
        assert result.rr > 0
        assert result.momentum > 0

    def test_web_intel_modifier(self) -> None:
        base = compute_score(rr_ratio=3.0)
        modified = compute_score(rr_ratio=3.0, web_intel_modifier=-0.10)
        assert modified.total < base.total

    def test_score_capped_at_100(self) -> None:
        result = compute_score(
            rr_ratio=10.0,
            rsi_val=60.0,
            rvol_val=5.0,
            ema_alignment=True,
            web_intel_modifier=0.5,
        )
        assert result.total <= 100.0

    def test_score_non_negative(self) -> None:
        result = compute_score(web_intel_modifier=-1.0)
        assert result.total >= 0.0
