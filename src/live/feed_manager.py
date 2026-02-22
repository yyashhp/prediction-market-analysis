"""Unified feed manager that orchestrates all data sources.

Produces a MarketSnapshot: a single point-in-time view of all active
markets across all venues, normalized and classified.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

from src.rv.classifier import Topic
from src.rv.edge import (
    Edge,
    compute_cross_venue_edge,
    compute_model_edge,
    compute_term_structure_edges,
    compute_threshold_edges,
)
from src.rv.liquidity import LiquidityFilter, passes_filter
from src.rv.matcher import detect_series, match_cross_venue
from src.rv.normalizer import NormalizedQuote

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """Point-in-time snapshot of all active markets across venues."""

    timestamp: datetime
    kalshi_quotes: list[NormalizedQuote] = field(default_factory=list)
    polymarket_quotes: list[NormalizedQuote] = field(default_factory=list)
    fetch_duration_seconds: float = 0.0

    @property
    def all_quotes(self) -> list[NormalizedQuote]:
        return self.kalshi_quotes + self.polymarket_quotes

    @property
    def total_count(self) -> int:
        return len(self.kalshi_quotes) + len(self.polymarket_quotes)

    def quotes_by_topic(self, topic: Topic) -> list[NormalizedQuote]:
        return [q for q in self.all_quotes if q.topic == topic.value]


@dataclass
class EdgeScanResult:
    """Results of scanning a snapshot for edges."""

    edges: list[Edge] = field(default_factory=list)
    filtered_quotes: int = 0
    total_quotes: int = 0
    scan_duration_seconds: float = 0.0

    @property
    def actionable_edges(self) -> list[Edge]:
        """Edges with spread_ratio >= 2 (at least 2 spreads of edge)."""
        return [e for e in self.edges if e.spread_ratio >= 2.0]

    def edges_by_topic(self, topic: Topic) -> list[Edge]:
        return [e for e in self.edges if e.topic == topic]

    def edges_by_type(self, edge_type: str) -> list[Edge]:
        return [e for e in self.edges if e.edge_type == edge_type]


class FeedManager:
    """Orchestrates data feeds and produces unified snapshots."""

    def __init__(
        self,
        kalshi_feed=None,
        polymarket_feed=None,
        liquidity_filter: LiquidityFilter | None = None,
        enabled_topics: list[Topic] | None = None,
        bankroll: float = 10000.0,
        kelly_fraction: float = 0.5,
    ):
        self.kalshi_feed = kalshi_feed
        self.polymarket_feed = polymarket_feed
        self.liquidity_filter = liquidity_filter or LiquidityFilter()
        self.enabled_topics = enabled_topics or [Topic.WEATHER, Topic.SPORTS, Topic.MACRO]
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction

    def snapshot(self) -> MarketSnapshot:
        """Fetch all sources and return a unified snapshot.

        Fetches from both venues in parallel (gracefully degrades if one is down),
        applies topic classification (already done in feeds).
        """
        start = time.monotonic()
        kalshi_quotes: list[NormalizedQuote] = []
        poly_quotes: list[NormalizedQuote] = []

        futures: dict = {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            if self.kalshi_feed:
                futures["kalshi"] = pool.submit(self.kalshi_feed.fetch_active_markets)
            if self.polymarket_feed:
                futures["poly"] = pool.submit(self.polymarket_feed.fetch_active_markets)

            for key, fut in futures.items():
                try:
                    result = fut.result()
                    if key == "kalshi":
                        kalshi_quotes = result
                    else:
                        poly_quotes = result
                except Exception as e:
                    logger.error("%s feed failed: %s", key, e)

        duration = time.monotonic() - start

        return MarketSnapshot(
            timestamp=datetime.now(),
            kalshi_quotes=kalshi_quotes,
            polymarket_quotes=poly_quotes,
            fetch_duration_seconds=duration,
        )

    def scan_edges(
        self,
        snapshot: MarketSnapshot,
        reference_probs: dict[str, float] | None = None,
    ) -> EdgeScanResult:
        """Scan a snapshot for all edge types.

        Args:
            snapshot: Market snapshot to analyze
            reference_probs: Optional dict of market_id → model probability
                for model-vs-market edge computation

        Returns:
            EdgeScanResult with all detected edges
        """
        start = time.monotonic()
        enabled_values = {t.value for t in self.enabled_topics}

        # Filter by topic and liquidity
        filtered_kalshi = [
            q for q in snapshot.kalshi_quotes if q.topic in enabled_values and passes_filter(q, self.liquidity_filter)
        ]
        filtered_poly = [
            q
            for q in snapshot.polymarket_quotes
            if q.topic in enabled_values and passes_filter(q, self.liquidity_filter)
        ]

        all_filtered = filtered_kalshi + filtered_poly
        all_edges: list[Edge] = []

        # 1. Cross-venue edges
        pairs = match_cross_venue(filtered_kalshi, filtered_poly)
        for pair in pairs:
            edge = compute_cross_venue_edge(
                pair,
                bankroll=self.bankroll,
                kelly_mult=self.kelly_fraction,
            )
            if edge:
                all_edges.append(edge)

        # 2. Term structure and threshold edges (per topic, per venue)
        for topic in self.enabled_topics:
            topic_quotes = [q for q in all_filtered if q.topic == topic.value]

            series_list = detect_series(topic_quotes, topic)
            for series in series_list:
                if series.series_type == "term_structure":
                    edges = compute_term_structure_edges(
                        series,
                        bankroll=self.bankroll,
                        kelly_mult=self.kelly_fraction,
                    )
                    all_edges.extend(edges)
                elif series.series_type == "threshold":
                    edges = compute_threshold_edges(
                        series,
                        bankroll=self.bankroll,
                        kelly_mult=self.kelly_fraction,
                    )
                    all_edges.extend(edges)

        # 3. Model-vs-market edges (if reference probabilities provided)
        if reference_probs:
            for q in all_filtered:
                if q.market_id in reference_probs:
                    edge = compute_model_edge(
                        q,
                        reference_probs[q.market_id],
                        bankroll=self.bankroll,
                        kelly_mult=self.kelly_fraction,
                    )
                    if edge:
                        all_edges.append(edge)

        # Sort by spread ratio descending (best edges first)
        all_edges.sort(key=lambda e: e.spread_ratio, reverse=True)

        duration = time.monotonic() - start

        return EdgeScanResult(
            edges=all_edges,
            filtered_quotes=len(all_filtered),
            total_quotes=snapshot.total_count,
            scan_duration_seconds=duration,
        )
