"""Price normalization across prediction market venues.

Converts Kalshi (integer cents 1-99) and Polymarket (decimal 0-1) prices
into a unified probability space for apples-to-apples comparison.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

# Month names used to strip trailing date tokens from Polymarket slugs
_SLUG_MONTHS = {
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
}


def _polymarket_group_slug(slug: str) -> str:
    """Extract a shared group key from a Polymarket market slug.

    Strips trailing month names and 4-digit years so that related series
    contracts share the same group key. For example:
        "will-the-fed-cut-rates-march-2026"  → "will-the-fed-cut-rates"
        "will-the-fed-cut-rates-april-2026"  → "will-the-fed-cut-rates"

    This enables term-structure series detection across Polymarket markets
    that represent the same event at different resolution dates.
    """
    if not slug:
        return slug
    tokens = slug.split("-")
    while tokens:
        last = tokens[-1].lower()
        if re.match(r"^\d{4}$", last) or last in _SLUG_MONTHS:
            tokens.pop()
        else:
            break
    return "-".join(tokens) if tokens else slug


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


def _clean_kalshi_title(market: dict) -> str:
    """Clean Kalshi market title for display.

    Multi-leg parlay markets have titles like "yes Josh Giddey: 15+,yes Josh Giddey: 6+"
    — these are outcome descriptions, not human-readable questions.
    Clean by stripping "yes "/"no " prefixes and joining with " & ".
    Also tries the subtitle field as fallback.
    """
    title = market.get("title", "")
    if not title:
        return title

    # Check if title looks like concatenated outcomes (starts with "yes " or "no ")
    lower = title.lower()
    if not (lower.startswith("yes ") or lower.startswith("no ")):
        return title

    # Prefer subtitle if it looks cleaner
    subtitle = market.get("subtitle", "")
    if subtitle and not subtitle.lower().startswith("yes "):
        return subtitle

    # Clean up: split on commas, strip "yes "/"no " prefix from each part
    parts = [p.strip() for p in title.split(",")]
    cleaned = []
    for p in parts:
        if p.lower().startswith("yes "):
            cleaned.append(p[4:])
        elif p.lower().startswith("no "):
            cleaned.append(p[3:])
        else:
            cleaned.append(p)
    return " & ".join(cleaned)


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

    # Use ticker (not event_ticker) for multi-game events so each parlay stays
    # in its own group — prevents spurious series detection across unrelated parlays.
    event_ticker = market.get("event_ticker", "")
    if "MULTIGAME" in event_ticker.upper():
        event_group = market.get("ticker", event_ticker)
    else:
        event_group = event_ticker

    return NormalizedQuote(
        market_id=market.get("ticker", ""),
        title=_clean_kalshi_title(market),
        venue="kalshi",
        topic="",  # assigned by classifier
        prob_mid=prob_mid,
        prob_bid=prob_bid,
        prob_ask=prob_ask,
        spread=spread,
        volume_24h=float(market.get("volume_24h", 0)),
        open_interest=int(market.get("open_interest", 0)),
        total_volume=float(market.get("volume", 0)),
        event_group=event_group,
        close_time=close_time,
        raw=market,
    )


def from_polymarket(market: dict) -> NormalizedQuote:
    """Normalize a Polymarket market dict to probability space.

    Polymarket prices are decimals (0-1) stored as JSON strings in outcome_prices.
    Bid/ask come from the gamma API's bestBid/bestAsk fields (present on liquid markets).
    OI is proxied by liquidity (genuinely not available from the gamma API).
    event_group uses _polymarket_group_slug to strip trailing month/year tokens so
    related series markets share a common group key for series detection.
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

    # Gamma API returns bestBid/bestAsk as floats or None
    best_bid = market.get("bestBid")
    best_ask = market.get("bestAsk")
    prob_bid = float(best_bid) if best_bid is not None else None
    prob_ask = float(best_ask) if best_ask is not None else None

    # Prefer the API's spread field if available, otherwise compute from bid/ask
    raw_spread = market.get("spread")
    if raw_spread is not None:
        spread = float(raw_spread)
    elif prob_bid is not None and prob_ask is not None:
        spread = prob_ask - prob_bid
    else:
        spread = None

    end_date = market.get("end_date", market.get("endDate"))
    close_time = None
    if isinstance(end_date, str) and end_date:
        try:
            close_time = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            close_time = None
    elif isinstance(end_date, datetime):
        close_time = end_date

    slug = market.get("slug", "")
    # Use liquidity as an OI proxy — it's the closest available metric from the gamma API
    liquidity = int(float(market.get("liquidity", 0) or 0))

    return NormalizedQuote(
        market_id=market.get("id", market.get("condition_id", "")),
        title=market.get("question", ""),
        venue="polymarket",
        topic="",
        prob_mid=prob_mid,
        prob_bid=prob_bid,
        prob_ask=prob_ask,
        spread=spread,
        volume_24h=float(market.get("volume24Hr") or market.get("volume24hr") or 0),
        open_interest=liquidity,  # proxy: liquidity ≈ depth; true OI not in gamma API
        total_volume=float(market.get("volume", 0) or 0),
        event_group=_polymarket_group_slug(slug),
        close_time=close_time,
        raw=market,
    )


def cents_to_prob(cents: int) -> float:
    """Convert Kalshi cents (1-99) to probability (0.01-0.99)."""
    return cents / 100.0


def prob_to_cents(prob: float) -> int:
    """Convert probability (0-1) to Kalshi cents (1-99), clamped."""
    return max(1, min(99, round(prob * 100)))
