from __future__ import annotations

from packages.core.models import ScanResult


def generate_watchlist_csv(scan_result: ScanResult) -> str:
    """Generate TradingView-compatible watchlist CSV."""
    lines = ["symbol,description"]
    for r in scan_result.results:
        desc = f"{r.direction.upper()} | RR:{r.setup.rr_ratio:.1f} | Score:{r.score.total:.0f}"
        lines.append(f"{r.symbol},{desc}")
    return "\n".join(lines) + "\n"


def generate_watchlist_comma(scan_result: ScanResult) -> str:
    """Generate comma-separated ticker list for TradingView."""
    symbols = [r.symbol for r in scan_result.results]
    return ",".join(symbols) + "\n" if symbols else "\n"
