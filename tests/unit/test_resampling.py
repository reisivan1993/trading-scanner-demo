from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from packages.core.models import OHLCVBar, Timeframe
from packages.core.resampling import (
    resample_1d_to_1w,
    resample_1m_to_15m,
    resample_1m_to_65m,
)


def _make_1m_bar(hour: int, minute: int, price: float, volume: int = 1000) -> OHLCVBar:
    return OHLCVBar(
        timestamp=datetime(2024, 2, 14, hour, minute),
        open=Decimal(str(price)),
        high=Decimal(str(price + 0.5)),
        low=Decimal(str(price - 0.5)),
        close=Decimal(str(price + 0.1)),
        volume=volume,
        timeframe=Timeframe.M1,
    )


def _make_daily_bar(year: int, month: int, day: int, price: float) -> OHLCVBar:
    return OHLCVBar(
        timestamp=datetime(year, month, day, 16, 0),
        open=Decimal(str(price)),
        high=Decimal(str(price + 2.0)),
        low=Decimal(str(price - 2.0)),
        close=Decimal(str(price + 1.0)),
        volume=10000,
        timeframe=Timeframe.D1,
    )


class TestResample1mTo15m:
    def test_basic_aggregation(self) -> None:
        bars = [_make_1m_bar(9, 30 + i, 170.0 + i * 0.1) for i in range(15)]
        result = resample_1m_to_15m(bars)

        assert len(result) == 1
        assert result[0].timeframe == Timeframe.M15
        assert result[0].open == bars[0].open
        assert result[0].close == bars[-1].close
        assert result[0].volume == sum(b.volume for b in bars)

    def test_multiple_groups(self) -> None:
        bars = [_make_1m_bar(9, 30 + i, 170.0) for i in range(30)]
        result = resample_1m_to_15m(bars)

        assert len(result) == 2

    def test_empty_input(self) -> None:
        assert resample_1m_to_15m([]) == []


class TestResample1mTo65m:
    def test_produces_six_bars_full_session(self) -> None:
        """Full trading session (09:30-16:00 = 390 min) should produce exactly 6 bars."""
        bars = []
        for i in range(390):
            h = 9 + (30 + i) // 60
            m = (30 + i) % 60
            if h >= 16:
                break
            bars.append(_make_1m_bar(h, m, 170.0 + i * 0.01))

        result = resample_1m_to_65m(bars)

        assert len(result) == 6
        for bar in result:
            assert bar.timeframe == Timeframe.M65

    def test_bar_boundaries_correct(self) -> None:
        """First bar starts at 09:30, second at 10:35."""
        bars = [
            _make_1m_bar(9, 30, 170.0),   # bar 0
            _make_1m_bar(10, 34, 171.0),   # bar 0 (last minute)
            _make_1m_bar(10, 35, 172.0),   # bar 1
            _make_1m_bar(11, 39, 173.0),   # bar 1 (last minute)
            _make_1m_bar(11, 40, 174.0),   # bar 2
        ]
        result = resample_1m_to_65m(bars)

        assert len(result) == 3
        assert result[0].open == Decimal("170.0")
        assert result[1].open == Decimal("172.0")
        assert result[2].open == Decimal("174.0")

    def test_ohlcv_aggregation_correct(self) -> None:
        bars = [
            _make_1m_bar(9, 30, 170.0, volume=100),
            _make_1m_bar(9, 31, 172.0, volume=200),
            _make_1m_bar(9, 32, 168.0, volume=300),
        ]
        result = resample_1m_to_65m(bars)

        assert len(result) == 1
        bar = result[0]
        assert bar.open == bars[0].open
        assert bar.close == bars[-1].close
        assert bar.high == max(b.high for b in bars)
        assert bar.low == min(b.low for b in bars)
        assert bar.volume == 600

    def test_empty_input(self) -> None:
        assert resample_1m_to_65m([]) == []


class TestResample1dTo1w:
    def test_single_week(self) -> None:
        bars = [
            _make_daily_bar(2024, 2, 12, 170.0),  # Monday
            _make_daily_bar(2024, 2, 13, 171.0),  # Tuesday
            _make_daily_bar(2024, 2, 14, 172.0),  # Wednesday
        ]
        result = resample_1d_to_1w(bars)

        assert len(result) == 1
        assert result[0].timeframe == Timeframe.W1
        assert result[0].volume == 30000

    def test_two_weeks(self) -> None:
        bars = [
            _make_daily_bar(2024, 2, 12, 170.0),  # Week 7
            _make_daily_bar(2024, 2, 13, 171.0),  # Week 7
            _make_daily_bar(2024, 2, 19, 173.0),  # Week 8
            _make_daily_bar(2024, 2, 20, 174.0),  # Week 8
        ]
        result = resample_1d_to_1w(bars)

        assert len(result) == 2

    def test_empty_input(self) -> None:
        assert resample_1d_to_1w([]) == []
