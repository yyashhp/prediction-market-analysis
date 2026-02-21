"""Tests for Kelly criterion position sizing."""

from __future__ import annotations

from src.rv.kelly import PositionLimits, kelly_fraction, size_position


class TestKellyFraction:
    def test_no_edge(self):
        assert kelly_fraction(edge=0.0, win_prob=0.5) == 0.0

    def test_negative_edge(self):
        assert kelly_fraction(edge=-0.05, win_prob=0.5) == 0.0

    def test_positive_edge_half_kelly(self):
        # Edge = 5pp, true prob = 0.55, market price = 0.50
        # Full Kelly: (0.55 - 0.50) / (1 - 0.50) = 0.10
        # Half Kelly: 0.05
        kf = kelly_fraction(edge=0.05, win_prob=0.55, fraction=0.5)
        assert abs(kf - 0.05) < 0.001

    def test_full_kelly(self):
        kf = kelly_fraction(edge=0.05, win_prob=0.55, fraction=1.0)
        assert abs(kf - 0.10) < 0.001

    def test_large_edge(self):
        # Edge = 20pp, true prob = 0.70, market = 0.50
        # Kelly: (0.70 - 0.50) / (1 - 0.50) = 0.40
        kf = kelly_fraction(edge=0.20, win_prob=0.70, fraction=1.0)
        assert abs(kf - 0.40) < 0.001

    def test_invalid_win_prob(self):
        assert kelly_fraction(edge=0.05, win_prob=0.0) == 0.0
        assert kelly_fraction(edge=0.05, win_prob=1.0) == 0.0

    def test_edge_larger_than_win_prob(self):
        """If edge > win_prob, market_price would be negative — return 0."""
        assert kelly_fraction(edge=0.60, win_prob=0.50) == 0.0


class TestSizePosition:
    def test_basic_sizing(self):
        size = size_position(
            edge=0.05,
            win_prob=0.55,
            bankroll=10000.0,
            fraction=0.5,
        )
        # Half-Kelly fraction = 0.05, so 0.05 * 10000 = $500
        assert abs(size - 500.0) < 1.0

    def test_per_contract_cap(self):
        limits = PositionLimits(max_per_contract=100.0)
        size = size_position(
            edge=0.05,
            win_prob=0.55,
            bankroll=10000.0,
            limits=limits,
            fraction=0.5,
        )
        assert size == 100.0

    def test_topic_cap(self):
        limits = PositionLimits(max_per_topic=200.0)
        size = size_position(
            edge=0.05,
            win_prob=0.55,
            bankroll=10000.0,
            limits=limits,
            current_topic_exposure=150.0,
            fraction=0.5,
        )
        assert size == 50.0  # 200 - 150 remaining

    def test_total_cap_exhausted(self):
        limits = PositionLimits(max_total=5000.0)
        size = size_position(
            edge=0.05,
            win_prob=0.55,
            bankroll=10000.0,
            limits=limits,
            current_total_exposure=5000.0,
            fraction=0.5,
        )
        assert size == 0.0

    def test_no_edge_returns_zero(self):
        size = size_position(edge=0.0, win_prob=0.5, bankroll=10000.0)
        assert size == 0.0
