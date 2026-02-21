"""Price normalization across prediction market venues.

Converts Kalshi (integer cents 1-99) and Polymarket (decimal 0-1) prices
into a unified probability space for apples-to-apples comparison.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NormalizedQuote:
    """A market quote normalized to probability space (0-1).

    All prices expressed as floats in [0, 1] representing implied probability.
    """

    market_id: str
    title: str
    venue: str  # "kalshi" or "polymarket"
    topic: str  # assigned by classifier
    prob_mid: float
    prob_bid: float | None = None
    prob_ask: float | None = None
    spread: float | None = None
    volume_24h: float = 0.0
    open_interest: int = 0
    total_volume: float = 0.0
    event_group: str = ""  # event_ticker (Kalshi) or slug group (Polymarket)
    close_time: datetime | None = None
    raw: dict = field(default_factory=dict)

    @property
    def has_quotes(self) -> bool:
        """Whether bid and ask are both available."""
        return self.prob_bid is not None and self.prob_ask is not None

    @property
    def prob_mid_or_last(self) -> float:
        """Best available probability estimate."""
        if self.has_quotes:
            return (self.prob_bid + self.prob_ask) / 2.0  # type: ignore[operator]
        return self.prob_mid


def from_kalshi(market: dict) -> NormalizedQuote:
    """Normalize a Kalshi market dict to probability space.

    Kalshi prices are integer cents (1-99). Divide by 100 for probability.
    """
    yes_bid = market.get("yes_bid")
    yes_ask = market.get("yes_ask")

    prob_bid = yes_bid / 100.0 if yes_bid is not None else None
    prob_ask = yes_ask / 100.0 if yes_ask is not None else None
    spread = (prob_ask - prob_bid) if (prob_bid is not None and prob_ask is not None) else None

    last_price = market.get("last_price")
    prob_mid = last_price / 100.0 if last_price is not None else 0.5

    # If we have bid/ask, use their midpoint as mid
    if prob_bid is not None and prob_ask is not None:
        prob_mid = (prob_bid + prob_ask) / 2.0

    close_time = market.get("close_time")
    if isinstance(close_time, str):
        try:
            close_time = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            close_time = None

    return NormalizedQuote(
        market_id=market.get("ticker", ""),
        title=market.get("title", ""),
        venue="kalshi",
        topic="",  # assigned by classifier
        prob_mid=prob_mid,
        prob_bid=prob_bid,
        prob_ask=prob_ask,
        spread=spread,
        volume_24h=float(market.get("volume_24h", 0)),
        open_interest=int(market.get("open_interest", 0)),
        total_volume=float(market.get("volume", 0)),
        event_group=market.get("event_ticker", ""),
        close_time=close_time,
        raw=market,
    )


def from_polymarket(market: dict) -> NormalizedQuote:
    """Normalize a Polymarket market dict to probability space.

    Polymarket prices are decimals (0-1) stored as JSON strings in outcome_prices.
    """
    outcome_prices_raw = market.get("outcome_prices", market.get("outcomePrices", "[]"))
    if isinstance(outcome_prices_raw, str):
        try:
            prices = json.loads(outcome_prices_raw)
        except (json.JSONDecodeError, TypeError):
            prices = []
    elif isinstance(outcome_prices_raw, list):
        prices = outcome_prices_raw
    else:
        prices = []

    # For binary markets, first outcome is "Yes" probability
    if len(prices) >= 2:
        prob_mid = float(prices[0])
    elif len(prices) == 1:
        prob_mid = float(prices[0])
    else:
        prob_mid = 0.5

    # Polymarket doesn't expose raw bid/ask in the gamma API — mid price only
    # The spread can be estimated from orderbook data if available
    best_bid = market.get("bestBid")
    best_ask = market.get("bestAsk")
    prob_bid = float(best_bid) if best_bid is not None else None
    prob_ask = float(best_ask) if best_ask is not None else None
    spread = (prob_ask - prob_bid) if (prob_bid is not None and prob_ask is not None) else None

    end_date = market.get("end_date", market.get("endDate"))
    close_time = None
    if isinstance(end_date, str) and end_date:
        try:
            close_time = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            close_time = None
    elif isinstance(end_date, datetime):
        close_time = end_date

    return NormalizedQuote(
        market_id=market.get("id", market.get("condition_id", "")),
        title=market.get("question", ""),
        venue="polymarket",
        topic="",
        prob_mid=prob_mid,
        prob_bid=prob_bid,
        prob_ask=prob_ask,
        spread=spread,
        volume_24h=0.0,  # Polymarket gamma API doesn't expose 24h volume directly
        open_interest=0,  # Not directly available from gamma API
        total_volume=float(market.get("volume", 0) or 0),
        event_group=market.get("slug", ""),
        close_time=close_time,
        raw=market,
    )


def cents_to_prob(cents: int) -> float:
    """Convert Kalshi cents (1-99) to probability (0.01-0.99)."""
    return cents / 100.0


def prob_to_cents(prob: float) -> int:
    """Convert probability (0-1) to Kalshi cents (1-99), clamped."""
    return max(1, min(99, round(prob * 100)))
