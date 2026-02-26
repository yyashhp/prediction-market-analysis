"""Market information efficiency classification.

For each prediction market contract, determines:
  - BackingSource: which external market or data model informs the bid/ask price
  - EdgeOpportunity: how exploitable the market is likely to be

The core insight: prediction market prices are only as good as the participants
setting them.  When a deep, liquid reference market exists (CME fed-funds futures,
Vegas sports lines, crypto perpetuals), sophisticated arbitrageurs quickly close
any gap → little edge available.  When no such reference exists (entertainment,
niche cultural events), prices are set by retail guessing → systematic analysis
can gain meaningful edge.

Edge-opportunity tiers:
  HIGH        No external reference; market makers are guessing.  Best edge.
  MEDIUM      A reference model exists (NWP weather, polling aggregators) but
              retail participants rarely consult it.  Edge if you have the model.
  LOW         Professional reference (sports books); slim edge for typical analyst.
  VERY_LOW    Deep liquid reference (CME futures, crypto exchanges); arb'd in minutes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.rv.normalizer import NormalizedQuote


class BackingSource(Enum):
    """External market or model that informs prediction market prices."""

    CME_FEDWATCH = "CME FedWatch"
    SPORTS_BOOKS = "Sports Books"
    CRYPTO_EXCHANGES = "Crypto Exchanges"
    WEATHER_MODELS = "NWP Models (ECMWF/GFS)"
    POLLING_AGGREGATORS = "Polling Aggregators"
    NONE = "None"


class EdgeOpportunity(Enum):
    """Edge potential versus the current prediction market price."""

    VERY_LOW = "Very Low"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass(frozen=True)
class InfoEfficiencyRating:
    backing_source: BackingSource
    edge_opportunity: EdgeOpportunity
    rationale: str


# ─── Keyword sets ─────────────────────────────────────────────────────────────

_FED_KEYWORDS: frozenset[str] = frozenset(
    [
        "fed ",
        "fomc",
        "federal reserve",
        "federal funds",
        "interest rate",
        "rate cut",
        "rate hike",
        "rate hold",
        "basis point",
        "bps cut",
        "feddecision",
        "feddec",
        "rate decision",
        "rate pause",
    ]
)

_CRYPTO_KEYWORDS: frozenset[str] = frozenset(
    [
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "solana",
        "sol",
        "xrp",
        "ripple",
        "dogecoin",
        "doge",
        "crypto",
        "blockchain",
        "defi",
        "nft",
        "all-time high",
        "ath",
        "100k",
        "200k",
        "stablecoin",
    ]
)

# Leagues / tournaments with deep professional sports-book coverage
_MAJOR_SPORTS_KEYWORDS: frozenset[str] = frozenset(
    [
        "nba",
        "nfl",
        "nhl",
        "mlb",
        "nascar",
        "pga",
        "ufc",
        "mma",
        "ncaa",
        "world cup",
        "champions league",
        "premier league",
        "la liga",
        "serie a",
        "bundesliga",
        "ligue 1",
        "eredivisie",
        "liga mx",
        "super bowl",
        "stanley cup",
        "world series",
        "nba finals",
        "march madness",
        "final four",
        "college football playoff",
        "wimbledon",
        "us open",
        "french open",
        "australian open",
        "grand slam",
        "formula 1",
        "f1",
        "grand prix",
        "indycar",
        "copa america",
        "euro 2024",
        "euro 2025",
        "euro 2026",
        "olympics",
        "world championship",
        "world athletics",
        "lakers",
        "celtics",
        "warriors",
        "bulls",
        "heat",
        "chiefs",
        "eagles",
        "cowboys",
        "patriots",
        "yankees",
        "dodgers",
        "red sox",
    ]
)

_WEATHER_KEYWORDS: frozenset[str] = frozenset(
    [
        "temperature",
        "precipitation",
        "hurricane",
        "typhoon",
        "cyclone",
        "snowfall",
        "snow",
        "rainfall",
        "rain",
        "storm",
        "tornado",
        "flood",
        "drought",
        "heat wave",
        "cold snap",
        "weather",
        "forecast",
        "degrees",
        "fahrenheit",
        "celsius",
        "inches of rain",
        "inches of snow",
    ]
)

_ENTERTAINMENT_KEYWORDS: frozenset[str] = frozenset(
    [
        "grammy",
        "oscar",
        "emmy",
        "golden globe",
        "academy award",
        "bafta",
        "tony award",
        "cannes",
        "sundance",
        "reality",
        "survivor",
        "bachelor",
        "bachelorette",
        "american idol",
        "got talent",
        "the voice",
        "big brother",
        "dancing with",
        "chart",
        "billboard",
        "number one",
        "album",
        "song",
        "music award",
        "box office",
        "streaming",
        "netflix",
        "spotify",
        "award show",
        "red carpet",
    ]
)

_POLLING_KEYWORDS: frozenset[str] = frozenset(
    [
        "election",
        "senate",
        "house ",
        "congress",
        "president",
        "governor",
        "mayor",
        "approval rating",
        "ballot",
        "primary",
        "runoff",
        "midterm",
        "general election",
        "vote ",
    ]
)


# ─── Ratings by source ────────────────────────────────────────────────────────

_RATING_CME = InfoEfficiencyRating(
    backing_source=BackingSource.CME_FEDWATCH,
    edge_opportunity=EdgeOpportunity.VERY_LOW,
    rationale=(
        "Fed-funds futures on CME carry billions in daily volume. CME FedWatch publishes "
        "exact implied probabilities for every upcoming FOMC meeting. Sophisticated "
        "arbitrageurs close any gap between CME and prediction markets within minutes."
    ),
)

_RATING_CRYPTO = InfoEfficiencyRating(
    backing_source=BackingSource.CRYPTO_EXCHANGES,
    edge_opportunity=EdgeOpportunity.VERY_LOW,
    rationale=(
        "Perpetual futures, options (Deribit, Binance), and on-chain analytics provide "
        "continuous consensus pricing 24/7. Multiple sophisticated participants actively "
        "arb any gap between spot/derivatives and prediction market prices."
    ),
)

_RATING_SPORTS_MAJOR = InfoEfficiencyRating(
    backing_source=BackingSource.SPORTS_BOOKS,
    edge_opportunity=EdgeOpportunity.LOW,
    rationale=(
        "Professional oddsmakers (Vegas, FanDuel, DraftKings, BetMGM) set calibrated lines "
        "with significant capital behind them. Prediction market prices closely track the "
        "vig-free implied probability. Beating well-covered sports lines is very hard."
    ),
)

_RATING_SPORTS_MINOR = InfoEfficiencyRating(
    backing_source=BackingSource.SPORTS_BOOKS,
    edge_opportunity=EdgeOpportunity.MEDIUM,
    rationale=(
        "Partial sports-book coverage for niche leagues, props, or international events. "
        "Lines may be thinner, set by less experienced oddsmakers. "
        "Opportunity exists with sport-specific data the books are not fully incorporating."
    ),
)

_RATING_WEATHER = InfoEfficiencyRating(
    backing_source=BackingSource.WEATHER_MODELS,
    edge_opportunity=EdgeOpportunity.MEDIUM,
    rationale=(
        "ECMWF and GFS ensemble NWP models provide calibrated probabilistic forecasts that "
        "far exceed retail intuition. Most prediction market participants do not consult "
        "professional model output — significant edge available via NWS/ECMWF API."
    ),
)

_RATING_POLLING = InfoEfficiencyRating(
    backing_source=BackingSource.POLLING_AGGREGATORS,
    edge_opportunity=EdgeOpportunity.MEDIUM,
    rationale=(
        "Polling aggregators (Silver Bulletin / FiveThirtyEight) provide probabilistic "
        "election estimates. Major national races are well-covered; niche primaries and "
        "local races have thinner polling, creating more opportunity."
    ),
)

_RATING_ENTERTAINMENT = InfoEfficiencyRating(
    backing_source=BackingSource.NONE,
    edge_opportunity=EdgeOpportunity.HIGH,
    rationale=(
        "No deep liquid reference market exists for awards/entertainment outcomes. "
        "Prices are set by retail participants without professional consensus. "
        "Systematic analysis (historical voting patterns, campaign spend, buzz metrics, "
        "industry insider signals) can achieve significant edge."
    ),
)

_RATING_UNKNOWN = InfoEfficiencyRating(
    backing_source=BackingSource.NONE,
    edge_opportunity=EdgeOpportunity.MEDIUM,
    rationale=(
        "No clear reference market identified. Could be an edge opportunity — "
        "investigate whether a deeper pricing source exists before trading."
    ),
)


# ─── Public API ───────────────────────────────────────────────────────────────


def _rate_info_efficiency(title: str, event_group: str, topic: str) -> InfoEfficiencyRating:
    """Core classification logic.  Accepts plain strings for easy testability."""
    combined = f"{title.lower()} {event_group.lower()}"
    topic_l = topic.lower()

    # Macro / Fed → CME FedWatch
    if topic_l == "macro" or any(kw in combined for kw in _FED_KEYWORDS):
        return _RATING_CME

    # Crypto → exchange derivatives
    if topic_l == "crypto" or any(kw in combined for kw in _CRYPTO_KEYWORDS):
        return _RATING_CRYPTO

    # Sports → major vs minor league coverage
    if topic_l == "sports":
        if any(kw in combined for kw in _MAJOR_SPORTS_KEYWORDS):
            return _RATING_SPORTS_MAJOR
        return _RATING_SPORTS_MINOR

    # Weather → NWP models
    if topic_l == "weather" or any(kw in combined for kw in _WEATHER_KEYWORDS):
        return _RATING_WEATHER

    # Entertainment / awards → no reference
    if topic_l == "entertainment" or any(kw in combined for kw in _ENTERTAINMENT_KEYWORDS):
        return _RATING_ENTERTAINMENT

    # Politics → polling aggregators
    if topic_l == "politics" or any(kw in combined for kw in _POLLING_KEYWORDS):
        return _RATING_POLLING

    # Fallback
    return _RATING_UNKNOWN


def classify_info_efficiency(quote: NormalizedQuote) -> InfoEfficiencyRating:
    """Return an InfoEfficiencyRating for a normalised prediction market quote."""
    return _rate_info_efficiency(
        title=quote.title or "",
        event_group=quote.event_group or "",
        topic=quote.topic or "",
    )
