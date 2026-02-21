"""Tests for market matching and series detection."""

from __future__ import annotations

from datetime import datetime

from src.rv.classifier import Topic
from src.rv.matcher import (
    _extract_threshold,
    _title_similarity,
    detect_series,
    match_cross_venue,
)
from src.rv.normalizer import NormalizedQuote


def _q(
    market_id: str = "TEST",
    title: str = "Test",
    venue: str = "kalshi",
    topic: str = "macro",
    prob_mid: float = 0.50,
    event_group: str = "",
    close_time: datetime | None = None,
    **kwargs,
) -> NormalizedQuote:
    return NormalizedQuote(
        market_id=market_id,
        title=title,
        venue=venue,
        topic=topic,
        prob_mid=prob_mid,
        event_group=event_group,
        close_time=close_time,
        **kwargs,
    )


class TestTitleSimilarity:
    def test_identical(self):
        assert _title_similarity("Will it rain?", "Will it rain?") == 1.0

    def test_similar(self):
        sim = _title_similarity(
            "Will the Fed cut rates in March 2026?",
            "Fed rate cut in March 2026",
        )
        assert sim > 0.7

    def test_different(self):
        sim = _title_similarity(
            "Will Bitcoin reach $200k?",
            "Lakers NBA championship winner",
        )
        assert sim < 0.3

    def test_empty_strings(self):
        assert _title_similarity("", "") == 0.0


class TestExtractThreshold:
    def test_above_percent(self):
        assert _extract_threshold("CPI above 3.0%") == 3.0

    def test_over_temperature(self):
        assert _extract_threshold("Temperature over 80 degrees") == 80.0

    def test_greater_than_dollar(self):
        assert _extract_threshold("Bitcoin greater than $100,000") == 100000.0

    def test_or_more(self):
        assert _extract_threshold("50 or more touchdowns") == 50.0

    def test_no_threshold(self):
        assert _extract_threshold("Will it rain tomorrow?") is None


class TestMatchCrossVenue:
    def test_fuzzy_match_same_topic(self):
        kalshi = [
            _q(
                market_id="FEDDECISION-MAR",
                title="Fed rate cut March 2026",
                venue="kalshi",
                topic="macro",
                prob_mid=0.45,
                close_time=datetime(2026, 3, 19),
            )
        ]
        poly = [
            _q(
                market_id="poly-fed-march",
                title="Fed rate cut in March 2026",
                venue="polymarket",
                topic="macro",
                prob_mid=0.50,
                close_time=datetime(2026, 3, 19),
            )
        ]
        pairs = match_cross_venue(kalshi, poly)
        assert len(pairs) == 1
        assert pairs[0].match_method == "fuzzy"
        assert pairs[0].kalshi.market_id == "FEDDECISION-MAR"
        assert pairs[0].polymarket.market_id == "poly-fed-march"

    def test_no_match_different_topic(self):
        kalshi = [_q(market_id="K1", title="NBA Lakers win", topic="sports")]
        poly = [_q(market_id="P1", title="NBA Lakers win", venue="polymarket", topic="macro")]
        pairs = match_cross_venue(kalshi, poly)
        assert len(pairs) == 0

    def test_no_match_dissimilar_titles(self):
        kalshi = [_q(market_id="K1", title="Bitcoin above 200k", topic="crypto")]
        poly = [
            _q(
                market_id="P1",
                title="Lakers win NBA championship",
                venue="polymarket",
                topic="crypto",
            )
        ]
        pairs = match_cross_venue(kalshi, poly)
        assert len(pairs) == 0

    def test_empty_lists(self):
        assert match_cross_venue([], []) == []


class TestDetectSeries:
    def test_term_structure_detection(self):
        quotes = [
            _q(
                market_id="FED-MAR",
                title="Fed cut by March",
                event_group="FEDDECISION",
                close_time=datetime(2026, 3, 19),
                prob_mid=0.30,
            ),
            _q(
                market_id="FED-MAY",
                title="Fed cut by May",
                event_group="FEDDECISION",
                close_time=datetime(2026, 5, 7),
                prob_mid=0.55,
            ),
            _q(
                market_id="FED-JUN",
                title="Fed cut by June",
                event_group="FEDDECISION",
                close_time=datetime(2026, 6, 18),
                prob_mid=0.70,
            ),
        ]
        series = detect_series(quotes, Topic.MACRO)
        assert len(series) == 1
        assert series[0].series_type == "term_structure"
        assert series[0].size == 3

    def test_threshold_series_detection(self):
        quotes = [
            _q(market_id="CPI-25", title="CPI above 2.5%", event_group="CPIYOY", prob_mid=0.80),
            _q(market_id="CPI-30", title="CPI above 3.0%", event_group="CPIYOY", prob_mid=0.50),
            _q(market_id="CPI-35", title="CPI above 3.5%", event_group="CPIYOY", prob_mid=0.20),
        ]
        series = detect_series(quotes, Topic.MACRO)
        assert len(series) == 1
        assert series[0].series_type == "threshold"
        assert series[0].size == 3

    def test_too_few_contracts(self):
        quotes = [
            _q(market_id="A", event_group="GRP", close_time=datetime(2026, 3, 1)),
            _q(market_id="B", event_group="GRP", close_time=datetime(2026, 4, 1)),
        ]
        series = detect_series(quotes, Topic.MACRO, min_series_size=3)
        assert len(series) == 0

    def test_different_groups_stay_separate(self):
        quotes = [
            _q(market_id="A1", event_group="GRP_A", close_time=datetime(2026, 1, 1), prob_mid=0.3),
            _q(market_id="A2", event_group="GRP_A", close_time=datetime(2026, 2, 1), prob_mid=0.5),
            _q(market_id="A3", event_group="GRP_A", close_time=datetime(2026, 3, 1), prob_mid=0.7),
            _q(market_id="B1", event_group="GRP_B", close_time=datetime(2026, 1, 1), prob_mid=0.2),
            _q(market_id="B2", event_group="GRP_B", close_time=datetime(2026, 2, 1), prob_mid=0.4),
            _q(market_id="B3", event_group="GRP_B", close_time=datetime(2026, 3, 1), prob_mid=0.6),
        ]
        series = detect_series(quotes, Topic.MACRO)
        assert len(series) == 2
