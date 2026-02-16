from __future__ import annotations

import logging
import re
from typing import Any

from packages.tools.quercle import QuercleTool

logger = logging.getLogger(__name__)

# Keyword patterns and their score modifiers
MODIFIERS: list[tuple[str, float, str]] = [
    (r"catalyst|upgrade|beat|outperform|raises?\s+guidance", +0.05, "Positive catalyst"),
    (r"downgrade|miss|warning|recall|cuts?\s+guidance", -0.07, "Negative sentiment"),
    (r"SEC|FDA|regulatory|lawsuit|investigation|probe", -0.08, "Regulatory risk"),
    (r"earnings|EPS|revenue\s+report|quarterly\s+results", -0.10, "Earnings proximity"),
    (r"short\s+interest|short\s+squeeze|heavily\s+shorted", -0.12, "Short interest concern"),
]

MIN_MODIFIER = -0.30
MAX_MODIFIER = 0.10


class WebIntelProcessor:
    """Processes web intelligence results into scoring modifiers."""

    def __init__(self, quercle: QuercleTool) -> None:
        self.quercle = quercle

    async def get_modifier(self, symbol: str) -> tuple[float, list[str]]:
        """Get score modifier and notes for a symbol.

        Returns:
            Tuple of (modifier capped to [-0.30, 0.10], list of note strings).
        """
        try:
            results = await self.quercle.search(symbol, "market_sentiment")
        except Exception:
            logger.warning("Web intel failed for %s", symbol, exc_info=True)
            return 0.0, ["Web intelligence unavailable"]

        if not results:
            return 0.0, []

        total_modifier = 0.0
        notes: list[str] = []
        matched_categories: set[str] = set()

        for item in results:
            text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()

            for pattern, modifier, label in MODIFIERS:
                if label in matched_categories:
                    continue
                if re.search(pattern, text, re.IGNORECASE):
                    total_modifier += modifier
                    notes.append(f"{label}: {item.get('title', 'N/A')}")
                    matched_categories.add(label)

        capped = max(MIN_MODIFIER, min(MAX_MODIFIER, total_modifier))
        return round(capped, 4), notes
