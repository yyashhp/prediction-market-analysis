"""Dashboard configuration loading.

Reads from config/dashboard.yaml (if present) and .env for secrets.
Falls back to sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from src.rv.classifier import Topic
from src.rv.kelly import PositionLimits
from src.rv.liquidity import LiquidityFilter

# Load .env from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")


@dataclass
class DashboardConfig:
    """Full dashboard configuration."""

    # Polling
    poll_interval: int = 60  # seconds between refreshes

    # Topics
    enabled_topics: list[Topic] = field(default_factory=lambda: [Topic.WEATHER, Topic.SPORTS, Topic.MACRO])

    # Liquidity
    liquidity: LiquidityFilter = field(default_factory=LiquidityFilter)

    # Edge thresholds
    min_edge_pp: float = 3.0  # minimum edge in probability points to display

    # Kelly / sizing
    bankroll: float = 10000.0
    kelly_fraction: float = 0.5
    position_limits: PositionLimits = field(default_factory=PositionLimits)

    # API credentials
    kalshi_api_key: str = ""
    kalshi_email: str = ""

    @classmethod
    def from_env(cls) -> DashboardConfig:
        """Build config from environment variables and defaults."""
        config = cls()
        config.kalshi_api_key = os.getenv("KALSHI_API_KEY", "")
        config.kalshi_email = os.getenv("KALSHI_EMAIL", "")

        # Override bankroll from env if set
        bankroll_str = os.getenv("RV_BANKROLL", "")
        if bankroll_str:
            try:
                config.bankroll = float(bankroll_str)
            except ValueError:
                pass

        # Override poll interval from env if set
        poll_str = os.getenv("RV_POLL_INTERVAL", "")
        if poll_str:
            try:
                config.poll_interval = int(poll_str)
            except ValueError:
                pass

        return config
