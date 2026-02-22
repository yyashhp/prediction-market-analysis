"""Tests for dashboard renderer (pure formatting functions)."""

from __future__ import annotations

from datetime import datetime

from src.dashboard.config import DashboardConfig
from src.dashboard.renderer import (
    render_dashboard,
    render_header,
    render_summary,
    render_topic_panel,
)
from src.live.feed_manager import EdgeScanResult, MarketSnapshot
from src.rv.classifier import Topic
from src.rv.edge import Edge
from src.rv.normalizer import NormalizedQuote


def _snap(**kwargs) -> MarketSnapshot:
    defaults = {
        "timestamp": datetime(2026, 2, 22, 12, 0, 0),
        "kalshi_quotes": [],
        "polymarket_quotes": [],
        "fetch_duration_seconds": 1.5,
    }
    defaults.update(kwargs)
    return MarketSnapshot(**defaults)


def _edge(**kwargs) -> Edge:
    defaults = {
        "edge_type": "cross_venue",
        "topic": Topic.MACRO,
        "magnitude_pp": 8.0,
        "spread_ratio": 2.5,
        "direction": "buy Kalshi @ 0.40, sell Poly @ 0.52",
        "contracts": [],
        "liquidity_grade": "B",
        "kelly_frac": 0.04,
        "kelly_size_usd": 400.0,
    }
    defaults.update(kwargs)
    return Edge(**defaults)


def _result(**kwargs) -> EdgeScanResult:
    defaults = {
        "edges": [],
        "filtered_quotes": 10,
        "total_quotes": 100,
        "scan_duration_seconds": 0.05,
    }
    defaults.update(kwargs)
    return EdgeScanResult(**defaults)


class TestRenderHeader:
    def test_contains_timestamp(self):
        snap = _snap(timestamp=datetime(2026, 2, 22, 12, 0, 0))
        out = render_header(snap, 10000.0)
        assert "2026-02-22 12:00:00" in out

    def test_contains_bankroll(self):
        out = render_header(_snap(), 5000.0)
        assert "5,000" in out

    def test_contains_market_counts(self):
        q = NormalizedQuote(market_id="T", title="T", venue="kalshi", topic="macro", prob_mid=0.5)
        snap = _snap(kalshi_quotes=[q, q], polymarket_quotes=[q])
        out = render_header(snap, 10000.0)
        assert "2 markets" in out  # Kalshi
        assert "1 markets" in out  # Polymarket


class TestRenderSummary:
    def test_shows_total_edges(self):
        result = _result(edges=[_edge(), _edge(spread_ratio=1.0)])
        out = render_summary(result)
        assert "2 found" in out

    def test_shows_actionable_count(self):
        # spread_ratio >= 2.0 is actionable
        result = _result(edges=[_edge(spread_ratio=3.0), _edge(spread_ratio=1.5)])
        out = render_summary(result)
        assert "1 actionable" in out

    def test_shows_kelly_total(self):
        result = _result(edges=[_edge(kelly_size_usd=300.0), _edge(kelly_size_usd=200.0)])
        out = render_summary(result)
        assert "500" in out


class TestRenderTopicPanel:
    def test_no_edges(self):
        out = render_topic_panel(Topic.MACRO, [])
        assert "no edges found" in out

    def test_with_edges(self):
        edge = _edge()
        out = render_topic_panel(Topic.MACRO, [edge])
        assert "MACRO" in out
        assert "8.0" in out  # magnitude_pp

    def test_edge_type_shown(self):
        edge = _edge(edge_type="term_structure")
        out = render_topic_panel(Topic.MACRO, [edge])
        assert "TermStr" in out


class TestRenderDashboard:
    def test_full_render(self):
        snap = _snap(
            kalshi_quotes=[NormalizedQuote(market_id="K1", title="T", venue="kalshi", topic="macro", prob_mid=0.5)],
            polymarket_quotes=[],
        )
        result = _result(
            edges=[_edge(topic=Topic.MACRO)],
            filtered_quotes=1,
            total_quotes=1,
        )
        out = render_dashboard(snap, result, [Topic.MACRO], bankroll=10000.0)
        assert "RV DASHBOARD" in out
        assert "MACRO" in out
        assert "Ctrl+C" in out

    def test_no_edges(self):
        out = render_dashboard(_snap(), _result(), [Topic.MACRO], bankroll=10000.0)
        assert "no edges found" in out


class TestDashboardConfig:
    def test_defaults(self):
        cfg = DashboardConfig()
        assert cfg.poll_interval == 60
        assert cfg.bankroll == 10000.0
        assert Topic.MACRO in cfg.enabled_topics
        assert Topic.WEATHER in cfg.enabled_topics

    def test_from_env_defaults(self):
        cfg = DashboardConfig.from_env()
        assert cfg.poll_interval == 60  # default when env var not set
