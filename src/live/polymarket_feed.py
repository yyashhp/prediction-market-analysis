"""Live Polymarket API feed for active markets and prices.

Uses the existing Polymarket gamma API client to poll for active markets
and normalize them into NormalizedQuote objects.
"""

from __future__ import annotations

import logging

from src.indexers.polymarket.client import PolymarketClient
from src.rv.classifier import classify_polymarket
from src.rv.normalizer import NormalizedQuote, from_polymarket

logger = logging.getLogger(__name__)


class PolymarketFeed:
    """Polls Polymarket gamma API for active markets."""

    def __init__(self, gamma_url: str | None = None):
        kwargs = {}
        if gamma_url:
            kwargs["gamma_url"] = gamma_url
        self.client = PolymarketClient(**kwargs)

    def close(self) -> None:
        self.client.close()

    def fetch_active_markets(self) -> list[NormalizedQuote]:
        """Fetch all active (non-closed) markets and return normalized quotes.

        Returns:
            List of NormalizedQuote objects with topic classification applied.
        """
        quotes: list[NormalizedQuote] = []

        try:
            offset = 0
            limit = 500

            while True:
                try:
                    markets = self.client.get_markets(limit=limit, offset=offset, active=True, closed=False)
                except Exception as e:
                    logger.error("Failed to fetch Polymarket markets at offset %d: %s", offset, e)
                    break

                if not markets:
                    break

                for market in markets:
                    try:
                        market_data = {
                            "id": market.id,
                            "condition_id": market.condition_id,
                            "question": market.question,
                            "slug": market.slug,
                            "outcome_prices": market.outcome_prices,
                            "volume": market.volume,
                            "liquidity": market.liquidity,
                            "active": market.active,
                            "closed": market.closed,
                            "endDate": market.end_date.isoformat() if market.end_date else None,
                        }
                        quote = from_polymarket(market_data)
                        topic = classify_polymarket(
                            question=market.question,
                            slug=market.slug,
                            market_id=market.id,
                        )
                        quote.topic = topic.value
                        quotes.append(quote)
                    except (KeyError, ValueError, TypeError) as e:
                        logger.debug("Skipping malformed Polymarket market: %s", e)
                        continue

                if len(markets) < limit:
                    break

                offset += len(markets)

        except Exception as e:
            logger.error("Failed to fetch Polymarket markets: %s", e)

        logger.info("Fetched %d Polymarket markets", len(quotes))
        return quotes
