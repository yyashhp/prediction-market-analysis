"""Tests for liquidity assessment and filtering."""

from __future__ import annotations

from src.rv.liquidity import LiquidityFilter, grade_liquidity, passes_filter
from src.rv.normalizer import NormalizedQuote


def _make_quote(**kwargs) -> NormalizedQuote:
    """Helper to build a NormalizedQuote with defaults."""
    defaults = {
        "market_id": "TEST",
        "title": "Test",
        "venue": "kalshi",
        "topic": "other",
        "prob_mid": 0.50,
        "prob_bid": 0.48,
        "prob_ask": 0.52,
        "spread": 0.04,
        "volume_24h": 1000.0,
        "open_interest": 500,
        "total_volume": 10000.0,
    }
    defaults.update(kwargs)
    return NormalizedQuote(**defaults)


class TestGradeLiquidity:
    def test_grade_a(self):
        q = _make_quote(spread=0.02, volume_24h=6000, open_interest=3000)
        assert grade_liquidity(q) == "A"

    def test_grade_b(self):
        q = _make_quote(spread=0.05, volume_24h=1000, open_interest=500)
        assert grade_liquidity(q) == "B"

    def test_grade_c(self):
        q = _make_quote(spread=0.15, volume_24h=100, open_interest=50)
        assert grade_liquidity(q) == "C"


class TestPassesFilter:
    def test_passes_default_filter(self):
        q = _make_quote(volume_24h=1000.0, spread=0.04, open_interest=500)
        assert passes_filter(q) is True

    def test_fails_volume(self):
        q = _make_quote(volume_24h=100.0, total_volume=100.0)
        assert passes_filter(q) is False

    def test_fails_spread(self):
        q = _make_quote(spread=0.15)
        assert passes_filter(q) is False

    def test_fails_oi(self):
        q = _make_quote(open_interest=50)
        assert passes_filter(q) is False

    def test_custom_thresholds(self):
        q = _make_quote(volume_24h=200.0, spread=0.12, open_interest=100)
        loose = LiquidityFilter(min_volume_24h=100, max_spread=0.15, min_open_interest=50)
        assert passes_filter(q, loose) is True

    def test_missing_spread_is_ok(self):
        """If spread is None (no bid/ask data), don't fail on spread check."""
        q = _make_quote(spread=None, prob_bid=None, prob_ask=None)
        assert passes_filter(q) is True

    def test_zero_volume_with_total_volume(self):
        """Polymarket doesn't report 24h volume; allow if total volume is high."""
        q = _make_quote(volume_24h=0.0, total_volume=50000.0)
        assert passes_filter(q) is True

    def test_zero_volume_with_low_total_volume(self):
        q = _make_quote(volume_24h=0.0, total_volume=100.0)
        assert passes_filter(q) is False
