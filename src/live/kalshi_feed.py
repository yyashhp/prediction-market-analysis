"""Live Kalshi API feed for active markets and quotes.

Uses the existing kalshi-python SDK client to poll for active markets
and normalize them into NormalizedQuote objects.

Two Kalshi endpoints are polled:
  - api.elections.kalshi.com   → elections markets (always accessible)
  - trading-api.kalshi.com     → non-elections markets (entertainment, sports,
                                  crypto, macro; GET /markets is publicly
                                  accessible without auth for browsing)

Results are deduplicated by ticker.
"""

from __future__ import annotations

import logging
import time

from src.indexers.kalshi.client import KALSHI_API_HOST, KALSHI_TRADING_HOST, KalshiClient
from src.rv.classifier import classify_kalshi
from src.rv.normalizer import NormalizedQuote, from_kalshi

logger = logging.getLogger(__name__)


class KalshiFeed:
    """Polls Kalshi API for active markets with current quotes.

    Pulls from both the elections subdomain (api.elections.kalshi.com) and
    the main trading API (trading-api.kalshi.com) so that all market types
    — elections, entertainment, sports, macro — are represented.
    """

    def __init__(self, host: str | None = None, also_poll_trading_api: bool = True):
        kwargs = {}
        if host:
            kwargs["host"] = host
        self.client = KalshiClient(**kwargs)

        # Second client for the main trading API (entertainment/sports/etc.)
        self._trading_client: KalshiClient | None = None
        if also_poll_trading_api and not host:
            # Only spin up trading client when using the default elections host
            try:
                self._trading_client = KalshiClient(host=KALSHI_TRADING_HOST)
            except Exception as e:
                logger.debug("Could not create trading API client: %s", e)

    def close(self) -> None:
        self.client.close()
        if self._trading_client:
            self._trading_client.close()

    def fetch_active_markets(self, status: str = "open", max_pages: int = 5) -> list[NormalizedQuote]:
        """Fetch active markets and return normalized quotes.

        Polls both the elections and trading APIs; deduplicates by ticker.

        Args:
            status: Market status filter (default: "open" for active markets)
            max_pages: Maximum pages per API endpoint (200 markets each).
        """
        seen_tickers: set[str] = set()
        quotes: list[NormalizedQuote] = []

        for label, client in [
            ("elections", self.client),
            ("trading", self._trading_client),
        ]:
            if client is None:
                continue
            try:
                cursor = None
                fetched = 0
                for _ in range(max_pages):
                    params: dict = {"limit": 200, "status": status}
                    if cursor:
                        params["cursor"] = cursor

                    data = client._get("/markets", params=params)
                    markets = data.get("markets", [])

                    for market_data in markets:
                        ticker = market_data.get("ticker", "")
                        if ticker in seen_tickers:
                            continue
                        seen_tickers.add(ticker)
                        try:
                            quote = from_kalshi(market_data)
                            topic = classify_kalshi(
                                event_ticker=market_data.get("event_ticker", ""),
                                ticker=ticker,
                                title=market_data.get("title", ""),
                            )
                            quote.topic = topic.value
                            quotes.append(quote)
                            fetched += 1
                        except (KeyError, ValueError, TypeError) as e:
                            logger.debug("Skipping malformed Kalshi market (%s): %s", label, e)
                            continue

                    cursor = data.get("cursor")
                    if not cursor or not markets:
                        break
                    time.sleep(0.35)  # stay well under Kalshi's rate limit

                logger.info("Fetched %d Kalshi markets from %s API", fetched, label)

            except Exception as e:
                logger.error("Failed to fetch Kalshi markets from %s API: %s", label, e)

        logger.info("Kalshi total: %d markets from both APIs", len(quotes))
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
