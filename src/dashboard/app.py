"""Main dashboard application entry point.

Runs a polling loop that fetches data, computes edges, and renders
the dashboard to the terminal.

Usage:
    uv run main.py dashboard
    uv run main.py dashboard --once   # single snapshot, no loop
"""

from __future__ import annotations

import sys
import time

from src.dashboard.config import DashboardConfig
from src.dashboard.renderer import clear_screen, render_dashboard
from src.live.feed_manager import FeedManager
from src.live.kalshi_feed import KalshiFeed
from src.live.polymarket_feed import PolymarketFeed


def create_feed_manager(config: DashboardConfig) -> FeedManager:
    """Create a FeedManager with live feeds from config."""
    kalshi = KalshiFeed()
    poly = PolymarketFeed()

    return FeedManager(
        kalshi_feed=kalshi,
        polymarket_feed=poly,
        liquidity_filter=config.liquidity,
        enabled_topics=config.enabled_topics,
        bankroll=config.bankroll,
        kelly_fraction=config.kelly_fraction,
    )


def run_once(config: DashboardConfig | None = None) -> None:
    """Run a single snapshot and print results."""
    if config is None:
        config = DashboardConfig.from_env()

    fm = create_feed_manager(config)

    print("Fetching markets...", file=sys.stderr)
    snapshot = fm.snapshot()

    print("Scanning for edges...", file=sys.stderr)
    result = fm.scan_edges(snapshot)

    output = render_dashboard(snapshot, result, config.enabled_topics, config.bankroll)
    print(output)


def run_loop(config: DashboardConfig | None = None) -> None:
    """Run the dashboard in a continuous polling loop."""
    if config is None:
        config = DashboardConfig.from_env()

    fm = create_feed_manager(config)

    print(f"Starting dashboard (poll interval: {config.poll_interval}s)...")
    print("Press Ctrl+C to exit.\n")

    try:
        while True:
            snapshot = fm.snapshot()
            result = fm.scan_edges(snapshot)

            clear_screen()
            output = render_dashboard(snapshot, result, config.enabled_topics, config.bankroll)
            print(output)

            time.sleep(config.poll_interval)

    except KeyboardInterrupt:
        print("\n\nDashboard stopped.")


def main(once: bool = False) -> None:
    """Dashboard entry point."""
    config = DashboardConfig.from_env()

    if once:
        run_once(config)
    else:
        run_loop(config)
