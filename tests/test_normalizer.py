"""Tests for price normalization across venues."""

from __future__ import annotations

from src.rv.normalizer import cents_to_prob, from_kalshi, from_polymarket, prob_to_cents


class TestFromKalshi:
    def test_basic_conversion(self):
        market = {
            "ticker": "PRES-2024-DJT",
            "title": "Will DJT win?",
            "event_ticker": "PRES",
            "yes_bid": 55,
            "yes_ask": 57,
            "last_price": 56,
            "volume": 10000,
            "volume_24h": 500,
            "open_interest": 1000,
        }
        q = from_kalshi(market)
        assert q.venue == "kalshi"
        assert q.market_id == "PRES-2024-DJT"
        assert q.prob_bid == 0.55
        assert q.prob_ask == 0.57
        assert q.prob_mid == (0.55 + 0.57) / 2  # mid from bid/ask
        assert abs(q.spread - 0.02) < 1e-10
        assert q.volume_24h == 500.0
        assert q.open_interest == 1000

    def test_missing_bid_ask(self):
        market = {
            "ticker": "TEST-001",
            "title": "Test",
            "event_ticker": "TEST",
            "last_price": 30,
            "volume": 100,
            "volume_24h": 0,
            "open_interest": 0,
        }
        q = from_kalshi(market)
        assert q.prob_bid is None
        assert q.prob_ask is None
        assert q.spread is None
        assert q.prob_mid == 0.30

    def test_close_time_parsing(self):
        market = {
            "ticker": "TEST-002",
            "title": "Test",
            "event_ticker": "TEST",
            "last_price": 50,
            "close_time": "2026-03-15T12:00:00Z",
            "volume": 0,
            "volume_24h": 0,
            "open_interest": 0,
        }
        q = from_kalshi(market)
        assert q.close_time is not None
        assert q.close_time.month == 3
        assert q.close_time.day == 15

    def test_prob_mid_or_last(self):
        market = {
            "ticker": "TEST-003",
            "title": "Test",
            "event_ticker": "TEST",
            "yes_bid": 40,
            "yes_ask": 50,
            "last_price": 42,
            "volume": 0,
            "volume_24h": 0,
            "open_interest": 0,
        }
        q = from_kalshi(market)
        # With bid/ask, mid_or_last should use bid/ask midpoint
        assert q.prob_mid_or_last == 0.45


class TestFromPolymarket:
    def test_basic_conversion(self):
        market = {
            "id": "poly-123",
            "question": "Will it rain tomorrow?",
            "slug": "will-it-rain-tomorrow",
            "outcome_prices": '["0.65", "0.35"]',
            "volume": 50000,
        }
        q = from_polymarket(market)
        assert q.venue == "polymarket"
        assert q.market_id == "poly-123"
        assert q.prob_mid == 0.65
        assert q.total_volume == 50000.0

    def test_camelcase_keys(self):
        """Polymarket API may return camelCase keys."""
        market = {
            "id": "poly-456",
            "question": "Test?",
            "outcomePrices": '["0.40", "0.60"]',
            "endDate": "2026-06-01T00:00:00Z",
            "volume": 1000,
        }
        q = from_polymarket(market)
        assert q.prob_mid == 0.40
        assert q.close_time is not None

    def test_list_prices(self):
        """Prices may come as actual list instead of JSON string."""
        market = {
            "id": "poly-789",
            "question": "Test?",
            "outcome_prices": [0.70, 0.30],
            "volume": 0,
        }
        q = from_polymarket(market)
        assert q.prob_mid == 0.70

    def test_missing_prices(self):
        market = {
            "id": "poly-000",
            "question": "Test?",
            "volume": 0,
        }
        q = from_polymarket(market)
        assert q.prob_mid == 0.5  # default


class TestHelpers:
    def test_cents_to_prob(self):
        assert cents_to_prob(50) == 0.50
        assert cents_to_prob(1) == 0.01
        assert cents_to_prob(99) == 0.99

    def test_prob_to_cents(self):
        assert prob_to_cents(0.50) == 50
        assert prob_to_cents(0.01) == 1
        assert prob_to_cents(0.99) == 99
        assert prob_to_cents(0.0) == 1  # clamped
        assert prob_to_cents(1.0) == 99  # clamped
