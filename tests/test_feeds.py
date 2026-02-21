"""Tests for live feeds and feed manager using mock data."""

from __future__ import annotations

from datetime import datetime

from src.live.feed_manager import EdgeScanResult, FeedManager, MarketSnapshot
from src.rv.classifier import Topic
from src.rv.liquidity import LiquidityFilter
from src.rv.normalizer import NormalizedQuote


def _q(
    market_id: str = "TEST",
    title: str = "Test",
    venue: str = "kalshi",
    topic: str = "macro",
    prob_mid: float = 0.50,
    spread: float = 0.04,
    volume_24h: float = 1000.0,
    open_interest: int = 500,
    total_volume: float = 10000.0,
    event_group: str = "",
    close_time: datetime | None = None,
) -> NormalizedQuote:
    prob_bid = prob_mid - spread / 2 if spread else None
    prob_ask = prob_mid + spread / 2 if spread else None
    return NormalizedQuote(
        market_id=market_id,
        title=title,
        venue=venue,
        topic=topic,
        prob_mid=prob_mid,
        prob_bid=prob_bid,
        prob_ask=prob_ask,
        spread=spread,
        volume_24h=volume_24h,
        open_interest=open_interest,
        total_volume=total_volume,
        event_group=event_group,
        close_time=close_time,
    )


class MockKalshiFeed:
    """Mock Kalshi feed that returns predetermined quotes."""

    def __init__(self, quotes: list[NormalizedQuote]):
        self._quotes = quotes

    def fetch_active_markets(self) -> list[NormalizedQuote]:
        return self._quotes


class MockPolymarketFeed:
    """Mock Polymarket feed that returns predetermined quotes."""

    def __init__(self, quotes: list[NormalizedQuote]):
        self._quotes = quotes

    def fetch_active_markets(self) -> list[NormalizedQuote]:
        return self._quotes


class TestMarketSnapshot:
    def test_total_count(self):
        snap = MarketSnapshot(
            timestamp=datetime.now(),
            kalshi_quotes=[_q(market_id="K1"), _q(market_id="K2")],
            polymarket_quotes=[_q(market_id="P1")],
        )
        assert snap.total_count == 3

    def test_quotes_by_topic(self):
        snap = MarketSnapshot(
            timestamp=datetime.now(),
            kalshi_quotes=[
                _q(market_id="K1", topic="macro"),
                _q(market_id="K2", topic="sports"),
            ],
            polymarket_quotes=[
                _q(market_id="P1", topic="macro"),
            ],
        )
        macro_quotes = snap.quotes_by_topic(Topic.MACRO)
        assert len(macro_quotes) == 2
        sports_quotes = snap.quotes_by_topic(Topic.SPORTS)
        assert len(sports_quotes) == 1


class TestFeedManager:
    def test_snapshot_with_both_feeds(self):
        kalshi = MockKalshiFeed([_q(market_id="K1")])
        poly = MockPolymarketFeed([_q(market_id="P1")])
        fm = FeedManager(kalshi_feed=kalshi, polymarket_feed=poly)

        snap = fm.snapshot()
        assert snap.total_count == 2
        assert len(snap.kalshi_quotes) == 1
        assert len(snap.polymarket_quotes) == 1

    def test_snapshot_kalshi_only(self):
        kalshi = MockKalshiFeed([_q(market_id="K1")])
        fm = FeedManager(kalshi_feed=kalshi)

        snap = fm.snapshot()
        assert snap.total_count == 1

    def test_snapshot_no_feeds(self):
        fm = FeedManager()
        snap = fm.snapshot()
        assert snap.total_count == 0

    def test_scan_cross_venue_edge(self):
        """Cross-venue edge: same market priced differently on Kalshi and Poly."""
        kalshi = MockKalshiFeed(
            [
                _q(market_id="K-FED", title="Fed rate cut March 2026", topic="macro", prob_mid=0.40, spread=0.04),
            ]
        )
        poly = MockPolymarketFeed(
            [
                _q(
                    market_id="P-FED",
                    title="Fed rate cut March 2026",
                    venue="polymarket",
                    topic="macro",
                    prob_mid=0.55,
                    spread=0.04,
                ),
            ]
        )
        fm = FeedManager(
            kalshi_feed=kalshi,
            polymarket_feed=poly,
            enabled_topics=[Topic.MACRO],
        )
        snap = fm.snapshot()
        result = fm.scan_edges(snap)

        assert isinstance(result, EdgeScanResult)
        # Should find cross-venue edge: 15pp raw, minus 4pp spreads = 11pp
        cross_edges = result.edges_by_type("cross_venue")
        assert len(cross_edges) >= 1
        assert cross_edges[0].magnitude_pp > 5.0

    def test_scan_filters_by_topic(self):
        """Markets in disabled topics should be excluded."""
        kalshi = MockKalshiFeed(
            [
                _q(market_id="K-POLI", topic="politics", prob_mid=0.40),
            ]
        )
        fm = FeedManager(
            kalshi_feed=kalshi,
            enabled_topics=[Topic.WEATHER, Topic.SPORTS, Topic.MACRO],
        )
        snap = fm.snapshot()
        result = fm.scan_edges(snap)
        assert result.filtered_quotes == 0

    def test_scan_filters_by_liquidity(self):
        """Illiquid markets should be excluded."""
        kalshi = MockKalshiFeed(
            [
                _q(market_id="K-THIN", topic="macro", volume_24h=10.0, total_volume=10.0, open_interest=5),
            ]
        )
        fm = FeedManager(
            kalshi_feed=kalshi,
            enabled_topics=[Topic.MACRO],
            liquidity_filter=LiquidityFilter(min_volume_24h=500),
        )
        snap = fm.snapshot()
        result = fm.scan_edges(snap)
        assert result.filtered_quotes == 0

    def test_scan_model_vs_market_edge(self):
        """Model reference probability should generate edges."""
        kalshi = MockKalshiFeed(
            [
                _q(market_id="WEATHER-1", title="High temp NYC > 80F", topic="weather", prob_mid=0.40, spread=0.04),
            ]
        )
        fm = FeedManager(
            kalshi_feed=kalshi,
            enabled_topics=[Topic.WEATHER],
        )
        snap = fm.snapshot()
        result = fm.scan_edges(snap, reference_probs={"WEATHER-1": 0.60})

        model_edges = result.edges_by_type("model_vs_market")
        assert len(model_edges) == 1
        # 20pp raw - 2pp half-spread = 18pp
        assert model_edges[0].magnitude_pp > 10.0

    def test_scan_term_structure_violation(self):
        """Term structure monotonicity violation should be detected."""
        kalshi = MockKalshiFeed(
            [
                _q(
                    market_id="FED-MAR",
                    title="Fed cut by March",
                    topic="macro",
                    prob_mid=0.55,
                    event_group="FEDDECISION",
                    close_time=datetime(2026, 3, 19),
                ),
                _q(
                    market_id="FED-MAY",
                    title="Fed cut by May",
                    topic="macro",
                    prob_mid=0.40,
                    event_group="FEDDECISION",
                    close_time=datetime(2026, 5, 7),
                ),
                _q(
                    market_id="FED-JUN",
                    title="Fed cut by June",
                    topic="macro",
                    prob_mid=0.70,
                    event_group="FEDDECISION",
                    close_time=datetime(2026, 6, 18),
                ),
            ]
        )
        fm = FeedManager(
            kalshi_feed=kalshi,
            enabled_topics=[Topic.MACRO],
        )
        snap = fm.snapshot()
        result = fm.scan_edges(snap)

        ts_edges = result.edges_by_type("term_structure")
        assert len(ts_edges) >= 1


class TestEdgeScanResult:
    def test_actionable_edges(self):
        result = EdgeScanResult(
            edges=[
                _make_edge(spread_ratio=3.0),
                _make_edge(spread_ratio=1.5),
                _make_edge(spread_ratio=2.5),
            ]
        )
        assert len(result.actionable_edges) == 2  # only >= 2.0


def _make_edge(spread_ratio: float = 1.0):
    from src.rv.edge import Edge

    return Edge(
        edge_type="cross_venue",
        topic=Topic.MACRO,
        magnitude_pp=5.0,
        spread_ratio=spread_ratio,
        direction="test",
    )
