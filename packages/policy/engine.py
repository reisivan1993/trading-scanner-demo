from __future__ import annotations

from typing import Any, Protocol

from packages.policy.schema import MergedPolicy


class HasPrice(Protocol):
    """Structural typing for items that expose price and volume attributes."""

    symbol: str
    price: float
    avg_dollar_volume_20d: float
    gap_pct: float | None


class PolicyEngine:
    """Applies policy rules at defined hook points in the scanning pipeline.

    Each hook takes a list of items and the active MergedPolicy, returning a
    filtered or transformed list.  Hooks that are not yet implemented act as
    pass-throughs.
    """

    def pre_filter_universe(
        self,
        items: list[Any],
        policy: MergedPolicy,
    ) -> list[Any]:
        """Filter universe candidates by price, volume, and gap-day rules."""
        filtered: list[Any] = []
        for item in items:
            if item.price < policy.universe.min_price:
                continue
            if item.avg_dollar_volume_20d < policy.universe.min_avg_dollar_volume_20d:
                continue
            if (
                policy.universe.exclude_gap_days.enabled
                and item.gap_pct is not None
                and abs(item.gap_pct) >= policy.universe.exclude_gap_days.gap_pct_threshold
            ):
                continue
            filtered.append(item)
        return filtered

    def post_features(
        self,
        items: list[Any],
        policy: MergedPolicy,
    ) -> list[Any]:
        """Hook after feature computation. Pass-through stub."""
        return items

    def pre_risk_gate(
        self,
        items: list[Any],
        policy: MergedPolicy,
    ) -> list[Any]:
        """Hook before risk gating. Pass-through stub."""
        return items

    def post_risk_gate(
        self,
        items: list[Any],
        policy: MergedPolicy,
    ) -> list[Any]:
        """Hook after risk gating. Pass-through stub."""
        return items

    def pre_score(
        self,
        items: list[Any],
        policy: MergedPolicy,
    ) -> list[Any]:
        """Hook before scoring. Pass-through stub."""
        return items

    def post_score(
        self,
        items: list[Any],
        policy: MergedPolicy,
    ) -> list[Any]:
        """Hook after scoring. Pass-through stub."""
        return items

    def pre_rank(
        self,
        items: list[Any],
        policy: MergedPolicy,
    ) -> list[Any]:
        """Hook before ranking. Pass-through stub."""
        return items

    def post_rank(
        self,
        items: list[Any],
        policy: MergedPolicy,
    ) -> list[Any]:
        """Hook after ranking. Pass-through stub."""
        return items
