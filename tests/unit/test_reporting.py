from __future__ import annotations

from decimal import Decimal

from packages.core.models import (
    ScanResult,
    ScanRunMeta,
    ScoringBreakdown,
    SetupResult,
    TradeSetup,
)
from packages.skills.reporting import generate_csv_report, generate_markdown_report
from packages.skills.tradingview_export import generate_watchlist_comma, generate_watchlist_csv


def _make_result() -> ScanResult:
    setup = TradeSetup(
        symbol="AAPL",
        direction="long",
        entry=Decimal("170.00"),
        stop=Decimal("167.00"),
        target_1=Decimal("176.00"),
        target_2=Decimal("179.00"),
        rr_ratio=2.0,
        shares=58,
        dollar_risk=Decimal("174.00"),
        dollar_pnl_t1=Decimal("348.00"),
        dollar_pnl_t2=Decimal("522.00"),
    )
    score = ScoringBreakdown(
        confluence=60.0, invalidation=50.0, rr=40.0,
        momentum=70.0, volume=80.0, pattern=50.0,
        cleanliness=65.0, web_intel_modifier=0.0, total=58.5,
    )
    result = SetupResult(
        symbol="AAPL", direction="long", setup=setup, score=score, rank=1,
    )
    return ScanResult(
        meta=ScanRunMeta(tickers_scanned=50, setups_found=10, setups_passed_risk=1),
        results=[result],
    )


class TestMarkdownReport:
    def test_english_report(self) -> None:
        report = generate_markdown_report(_make_result(), language="en")
        assert "AAPL" in report
        assert "Cold Trader Scanner Report" in report

    def test_hebrew_report(self) -> None:
        report = generate_markdown_report(_make_result(), language="he")
        assert "AAPL" in report
        assert "סורק" in report

    def test_cash_is_position_banner(self) -> None:
        result = ScanResult(
            meta=ScanRunMeta(), results=[], cash_is_position=True,
        )
        report = generate_markdown_report(result, language="en")
        assert "CASH IS A POSITION" in report

    def test_verbose_report_has_breakdown(self) -> None:
        report = generate_markdown_report(_make_result(), language="en", verbosity="full")
        assert "Scoring Breakdown" in report


class TestCsvReport:
    def test_csv_has_header_and_data(self) -> None:
        csv_str = generate_csv_report(_make_result())
        lines = csv_str.strip().split("\n")
        assert len(lines) == 2
        assert "AAPL" in lines[1]


class TestTradingViewExport:
    def test_watchlist_csv(self) -> None:
        csv_str = generate_watchlist_csv(_make_result())
        assert "AAPL" in csv_str
        assert "LONG" in csv_str

    def test_watchlist_comma(self) -> None:
        comma_str = generate_watchlist_comma(_make_result())
        assert comma_str.strip() == "AAPL"

    def test_empty_watchlist(self) -> None:
        result = ScanResult(meta=ScanRunMeta(), results=[])
        assert generate_watchlist_comma(result).strip() == ""
