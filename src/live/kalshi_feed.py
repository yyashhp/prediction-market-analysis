"""Live Kalshi API feed for active markets and quotes.

Uses the existing kalshi-python SDK client to poll for active markets
and normalize them into NormalizedQuote objects.
"""

from __future__ import annotations

import logging
import time

from src.indexers.kalshi.client import KalshiClient
from src.rv.classifier import classify_kalshi
from src.rv.normalizer import NormalizedQuote, from_kalshi

logger = logging.getLogger(__name__)


class KalshiFeed:
    """Polls Kalshi API for active markets with current quotes."""

    def __init__(self, host: str | None = None):
        kwargs = {}
        if host:
            kwargs["host"] = host
        self.client = KalshiClient(**kwargs)

    def close(self) -> None:
        self.client.close()

    def fetch_active_markets(self, status: str = "open", max_pages: int = 5) -> list[NormalizedQuote]:
        """Fetch active markets and return normalized quotes.

        Args:
            status: Market status filter (default: "open" for active markets)
            max_pages: Maximum number of pages to fetch (200 markets each).
                Caps at 1000 markets by default — sufficient for finding edges
                without paginating through thousands of illiquid tail markets.

        Returns:
            List of NormalizedQuote objects with topic classification applied.
        """
        quotes: list[NormalizedQuote] = []

        try:
            cursor = None
            for _ in range(max_pages):
                params: dict = {"limit": 200, "status": status}
                if cursor:
                    params["cursor"] = cursor

                data = self.client._get("/markets", params=params)
                markets = data.get("markets", [])

                for market_data in markets:
                    try:
                        quote = from_kalshi(market_data)
                        # Apply topic classification
                        topic = classify_kalshi(
                            event_ticker=market_data.get("event_ticker", ""),
                            ticker=market_data.get("ticker", ""),
                            title=market_data.get("title", ""),
                        )
                        quote.topic = topic.value
                        quotes.append(quote)
                    except (KeyError, ValueError, TypeError) as e:
                        logger.debug("Skipping malformed Kalshi market: %s", e)
                        continue

                cursor = data.get("cursor")
                if not cursor or not markets:
                    break
                time.sleep(0.35)  # stay well under Kalshi's rate limit between pages

        except Exception as e:
            logger.error("Failed to fetch Kalshi markets: %s", e)

        logger.info("Fetched %d Kalshi markets", len(quotes))
        return quotes

    def fetch_markets_by_event(self, event_ticker: str) -> list[NormalizedQuote]:
        """Fetch all markets under a specific event ticker.

        Useful for building series (term structure, threshold) within an event.
        """
        quotes: list[NormalizedQuote] = []

        try:
            markets = self.client.list_markets(limit=200, event_ticker=event_ticker)
            for market in markets:
                market_data = {
                    "ticker": market.ticker,
                    "event_ticker": market.event_ticker,
                    "title": market.title,
                    "yes_bid": market.yes_bid,
                    "yes_ask": market.yes_ask,
                    "last_price": market.last_price,
                    "volume": market.volume,
                    "volume_24h": market.volume_24h,
                    "open_interest": market.open_interest,
                    "close_time": market.close_time.isoformat() if market.close_time else None,
                    "status": market.status,
                    "result": market.result,
                }
                quote = from_kalshi(market_data)
                topic = classify_kalshi(
                    event_ticker=market.event_ticker,
                    ticker=market.ticker,
                    title=market.title,
                )
                quote.topic = topic.value
                quotes.append(quote)

        except Exception as e:
            logger.error("Failed to fetch Kalshi event %s: %s", event_ticker, e)

        return quotes
