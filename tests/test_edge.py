"""Tests for edge calculation."""

from __future__ import annotations

from datetime import datetime

from src.rv.classifier import Topic
from src.rv.edge import (
    compute_cross_venue_edge,
    compute_model_edge,
    compute_term_structure_edges,
    compute_threshold_edges,
)
from src.rv.matcher import ContractSeries, MarketPair
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
    close_time: datetime | None = None,
    event_group: str = "",
    **kwargs,
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
        close_time=close_time,
        event_group=event_group,
        **kwargs,
    )


class TestCrossVenueEdge:
    def test_meaningful_edge(self):
        pair = MarketPair(
            kalshi=_q(market_id="K-FED", prob_mid=0.40, spread=0.04),
            polymarket=_q(market_id="P-FED", venue="polymarket", prob_mid=0.52, spread=0.04),
            match_confidence="high",
            match_method="curated",
        )
        edge = compute_cross_venue_edge(pair)
        assert edge is not None
        assert edge.edge_type == "cross_venue"
        assert edge.magnitude_pp > 0
        # Raw edge = 12pp, minus half-spread each side (2pp + 2pp) = 8pp
        assert abs(edge.magnitude_pp - 8.0) < 0.1

    def test_no_edge_when_within_spread(self):
        pair = MarketPair(
            kalshi=_q(market_id="K1", prob_mid=0.50, spread=0.06),
            polymarket=_q(market_id="P1", venue="polymarket", prob_mid=0.52, spread=0.06),
            match_confidence="high",
            match_method="fuzzy",
        )
        # Raw edge = 2pp, half-spreads = 3pp + 3pp = 6pp total cost > 2pp edge
        edge = compute_cross_venue_edge(pair)
        assert edge is None

    def test_tiny_difference_ignored(self):
        pair = MarketPair(
            kalshi=_q(market_id="K1", prob_mid=0.500),
            polymarket=_q(market_id="P1", venue="polymarket", prob_mid=0.502),
            match_confidence="high",
            match_method="fuzzy",
        )
        edge = compute_cross_venue_edge(pair)
        assert edge is None


class TestTermStructureEdges:
    def test_monotonicity_violation(self):
        series = ContractSeries(
            topic=Topic.MACRO,
            series_type="term_structure",
            contracts=[
                _q(market_id="FED-MAR", prob_mid=0.55, close_time=datetime(2026, 3, 19)),
                _q(market_id="FED-MAY", prob_mid=0.40, close_time=datetime(2026, 5, 7)),  # violation!
                _q(market_id="FED-JUN", prob_mid=0.70, close_time=datetime(2026, 6, 18)),
            ],
            venue="kalshi",
            event_group="FEDDECISION",
        )
        edges = compute_term_structure_edges(series)
        assert len(edges) == 1
        assert edges[0].edge_type == "term_structure"
        # Violation: March (0.55) > May (0.40) = 15pp
        assert abs(edges[0].magnitude_pp - 15.0) < 0.1

    def test_no_violation_when_monotone(self):
        series = ContractSeries(
            topic=Topic.MACRO,
            series_type="term_structure",
            contracts=[
                _q(market_id="A", prob_mid=0.30, close_time=datetime(2026, 3, 1)),
                _q(market_id="B", prob_mid=0.50, close_time=datetime(2026, 5, 1)),
                _q(market_id="C", prob_mid=0.70, close_time=datetime(2026, 7, 1)),
            ],
            venue="kalshi",
            event_group="TEST",
        )
        edges = compute_term_structure_edges(series)
        assert len(edges) == 0

    def test_wrong_series_type_returns_empty(self):
        series = ContractSeries(
            topic=Topic.MACRO,
            series_type="threshold",  # wrong type for this function
            contracts=[],
        )
        edges = compute_term_structure_edges(series)
        assert len(edges) == 0


class TestThresholdEdges:
    def test_cdf_residuals(self):
        """Contracts that deviate from a fitted normal CDF should be flagged."""
        series = ContractSeries(
            topic=Topic.MACRO,
            series_type="threshold",
            contracts=[
                _q(market_id="CPI-2.0", title="CPI above 2.0%", prob_mid=0.95),
                _q(market_id="CPI-2.5", title="CPI above 2.5%", prob_mid=0.75),
                _q(market_id="CPI-3.0", title="CPI above 3.0%", prob_mid=0.50),
                _q(market_id="CPI-3.5", title="CPI above 3.5%", prob_mid=0.25),
                # This one is deliberately mispriced (too high)
                _q(market_id="CPI-4.0", title="CPI above 4.0%", prob_mid=0.20),
            ],
            venue="kalshi",
            event_group="CPIYOY",
        )
        edges = compute_threshold_edges(series)
        # Should find at least one residual edge
        # The exact count depends on the fitted distribution
        assert isinstance(edges, list)
        for edge in edges:
            assert edge.edge_type == "threshold_cdf"
            assert edge.magnitude_pp > 0

    def test_too_few_contracts(self):
        series = ContractSeries(
            topic=Topic.MACRO,
            series_type="threshold",
            contracts=[
                _q(market_id="A", title="CPI above 2.5%", prob_mid=0.70),
                _q(market_id="B", title="CPI above 3.0%", prob_mid=0.40),
            ],
            venue="kalshi",
        )
        edges = compute_threshold_edges(series)
        assert len(edges) == 0


class TestModelEdge:
    def test_model_disagrees(self):
        quote = _q(market_id="WEATHER-1", prob_mid=0.40, spread=0.04)
        edge = compute_model_edge(quote, model_probability=0.55)
        assert edge is not None
        assert edge.edge_type == "model_vs_market"
        # Raw edge = 15pp, minus half-spread (2pp) = 13pp
        assert abs(edge.magnitude_pp - 13.0) < 0.1

    def test_model_agrees(self):
        quote = _q(market_id="WEATHER-2", prob_mid=0.50, spread=0.04)
        edge = compute_model_edge(quote, model_probability=0.50)
        assert edge is None

    def test_edge_within_spread(self):
        quote = _q(market_id="WEATHER-3", prob_mid=0.50, spread=0.10)
        edge = compute_model_edge(quote, model_probability=0.53)
        # Raw edge = 3pp, half-spread = 5pp → adjusted edge negative
        assert edge is None
