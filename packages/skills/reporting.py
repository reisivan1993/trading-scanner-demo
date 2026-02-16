from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Literal

from packages.core.models import ScanResult, SetupResult

# Hebrew column headers mapping
HEBREW_HEADERS = {
    "Rank": "דירוג",
    "Symbol": "סימול",
    "Direction": "כיוון",
    "Entry": "כניסה",
    "Stop": "סטופ",
    "Target 1": "יעד 1",
    "Target 2": "יעד 2",
    "RR": "סיכון/סיכוי",
    "Shares": "מניות",
    "Risk $": "סיכון $",
    "PnL T1 $": "רווח T1 $",
    "Score": "ציון",
    "Patterns": "תבניות",
}

ENGLISH_HEADERS = {k: k for k in HEBREW_HEADERS}

DIRECTION_HE = {"long": "לונג", "short": "שורט"}


def _get_headers(language: str) -> dict[str, str]:
    return HEBREW_HEADERS if language == "he" else ENGLISH_HEADERS


def _format_direction(direction: str, language: str) -> str:
    if language == "he":
        return DIRECTION_HE.get(direction, direction)
    return direction.upper()


def generate_markdown_report(
    scan_result: ScanResult,
    language: Literal["en", "he"] = "en",
    verbosity: str = "medium",
) -> str:
    """Generate a markdown report from scan results."""
    headers = _get_headers(language)
    lines: list[str] = []

    # Title
    title = "Cold Trader Scanner Report" if language == "en" else "דוח סורק Cold Trader"
    lines.append(f"# {title}")
    lines.append("")

    # Banner
    if scan_result.cash_is_position:
        banner = (
            "**CASH IS A POSITION** - No setups passed all filters."
            if language == "en"
            else "**מזומן הוא פוזיציה** - אין סטאפים שעברו את כל הפילטרים."
        )
        lines.append(f"> {banner}")
        lines.append("")

    # Meta
    meta = scan_result.meta
    lines.append(f"**Run ID:** {meta.run_id}")
    lines.append(f"**Scanned:** {meta.tickers_scanned} tickers")
    lines.append(f"**Setups found:** {meta.setups_found}")
    lines.append(f"**Passed risk gate:** {meta.setups_passed_risk}")
    lines.append("")

    if not scan_result.results:
        return "\n".join(lines)

    # Table header
    cols = ["Rank", "Symbol", "Direction", "Entry", "Stop", "Target 1", "RR", "Score"]
    if verbosity in ("medium", "full"):
        cols.extend(["Shares", "Risk $", "PnL T1 $"])
    if verbosity == "full":
        cols.append("Patterns")

    header_row = "| " + " | ".join(headers.get(c, c) for c in cols) + " |"
    separator = "| " + " | ".join("---" for _ in cols) + " |"
    lines.append(header_row)
    lines.append(separator)

    # Table rows
    for r in scan_result.results:
        row_data: dict[str, str] = {
            "Rank": str(r.rank),
            "Symbol": r.symbol,
            "Direction": _format_direction(r.direction, language),
            "Entry": f"${r.setup.entry}",
            "Stop": f"${r.setup.stop}",
            "Target 1": f"${r.setup.target_1}",
            "RR": f"{r.setup.rr_ratio:.1f}",
            "Score": f"{r.score.total:.1f}",
            "Shares": str(r.setup.shares),
            "Risk $": f"${r.setup.dollar_risk}",
            "PnL T1 $": f"${r.setup.dollar_pnl_t1}",
            "Patterns": ", ".join(p.name for p in r.patterns) if r.patterns else "-",
        }
        row = "| " + " | ".join(row_data.get(c, "") for c in cols) + " |"
        lines.append(row)

    lines.append("")

    # Scoring breakdown for top setups (verbose)
    if verbosity == "full" and scan_result.results:
        lines.append("## Scoring Breakdown")
        lines.append("")
        for r in scan_result.results[:5]:
            lines.append(f"### {r.symbol} ({_format_direction(r.direction, language)})")
            s = r.score
            lines.append(f"- Confluence: {s.confluence:.1f}")
            lines.append(f"- Invalidation: {s.invalidation:.1f}")
            lines.append(f"- R:R: {s.rr:.1f}")
            lines.append(f"- Momentum: {s.momentum:.1f}")
            lines.append(f"- Volume: {s.volume:.1f}")
            lines.append(f"- Pattern: {s.pattern:.1f}")
            lines.append(f"- Cleanliness: {s.cleanliness:.1f}")
            if s.web_intel_modifier != 0:
                lines.append(f"- Web Intel Modifier: {s.web_intel_modifier:+.2f}")
            lines.append(f"- **Total: {s.total:.1f}**")
            lines.append("")

    return "\n".join(lines)


def generate_csv_report(scan_result: ScanResult) -> str:
    """Generate a CSV string from scan results."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Rank", "Symbol", "Direction", "Entry", "Stop", "Target1", "Target2",
        "RR", "Shares", "Risk", "PnL_T1", "PnL_T2", "Score",
    ])

    for r in scan_result.results:
        writer.writerow([
            r.rank,
            r.symbol,
            r.direction,
            r.setup.entry,
            r.setup.stop,
            r.setup.target_1,
            r.setup.target_2 or "",
            r.setup.rr_ratio,
            r.setup.shares,
            r.setup.dollar_risk,
            r.setup.dollar_pnl_t1,
            r.setup.dollar_pnl_t2 or "",
            r.score.total,
        ])

    return output.getvalue()
