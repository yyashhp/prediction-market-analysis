"""Topic classification for prediction market contracts.

Maps Kalshi event_ticker prefixes and Polymarket question text into
standardized topics for organizing the dashboard.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path

from src.analysis.kalshi.util.categories import SUBCATEGORY_PATTERNS


class Topic(Enum):
    """High-level topic categories for prediction markets."""

    WEATHER = "weather"
    SPORTS = "sports"
    MACRO = "macro"  # Fed, CPI, GDP, economic indicators
    CRYPTO = "crypto"
    POLITICS = "politics"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


# Map the existing categories.py group names to our Topic enum
_GROUP_TO_TOPIC = {
    "Weather": Topic.WEATHER,
    "Sports": Topic.SPORTS,
    "Esports": Topic.SPORTS,  # group esports with sports
    "Finance": Topic.MACRO,
    "Crypto": Topic.CRYPTO,
    "Politics": Topic.POLITICS,
    "Entertainment": Topic.ENTERTAINMENT,
    "Media": Topic.ENTERTAINMENT,
    "Science/Tech": Topic.OTHER,
    "World Events": Topic.OTHER,
    "Other": Topic.OTHER,
}

# Keyword patterns for Polymarket question classification
# Order matters: more specific patterns first. Politics and entertainment
# must come before sports to avoid "win" false positives (e.g., "win the Senate").
_POLYMARKET_PATTERNS: list[tuple[re.Pattern[str], Topic]] = [
    # Weather (very specific keywords, check first)
    (
        re.compile(r"\b(temperature|weather|rain|snow|hurricane|tornado|heat wave|cold wave|forecast)\b", re.I),
        Topic.WEATHER,
    ),
    # Macro/Finance (check before politics — "Fed" is unambiguous)
    (
        re.compile(
            r"\b(Fed\b|Federal Reserve|interest rate|rate cut|rate hike|CPI|inflation|GDP|"
            r"unemployment|payrolls|S&P 500|NASDAQ|treasury|bond yield|tariff|recession|"
            r"FedWatch|FOMC|PCE|debt ceiling|jobs report)\b",
            re.I,
        ),
        Topic.MACRO,
    ),
    # Crypto (unambiguous keywords)
    (
        re.compile(
            r"\b(Bitcoin|BTC|Ethereum|ETH|crypto|Solana|SOL|Dogecoin|DOGE|XRP|blockchain|"
            r"token|DeFi|NFT|stablecoin)\b",
            re.I,
        ),
        Topic.CRYPTO,
    ),
    # Politics (check before sports — "Senate", "Congress", "election" are unambiguous)
    (
        re.compile(
            r"\b(president|election|Senate|Congress|House of Representatives|Democrat|Republican|"
            r"governor|mayor|primary|nominee|cabinet|impeach|legislation|bill pass|"
            r"Trump|Biden|poll|approval rating|political party)\b",
            re.I,
        ),
        Topic.POLITICS,
    ),
    # Entertainment (check before sports — "Oscar", "Grammy" are unambiguous)
    (
        re.compile(
            r"\b(Oscar|Grammy|Emmy|Netflix|Spotify|movie|film|album|song|Billboard|"
            r"box office|Rotten Tomatoes|streaming|TV show|series finale|concert|"
            r"Best Picture|Best Actor|Best Actress)\b",
            re.I,
        ),
        Topic.ENTERTAINMENT,
    ),
    # Sports (last among content topics — "win" is too generic)
    (
        re.compile(
            r"\b(NFL|NBA|MLB|NHL|UFC|Super Bowl|World Series|Stanley Cup|Premier League|Champions League|"
            r"FIFA|tennis|golf|PGA|F1|NASCAR|boxing|MMA|World Cup|Olympics|NCAA|March Madness|"
            r"playoff|championship|MVP|touchdown|home run|goal scored|win the game)\b",
            re.I,
        ),
        Topic.SPORTS,
    ),
]

# Cache for overrides file
_overrides_cache: dict[str, Topic] | None = None


def _load_overrides(path: Path | None = None) -> dict[str, Topic]:
    """Load topic override mappings from JSON file."""
    global _overrides_cache
    if _overrides_cache is not None:
        return _overrides_cache

    if path is None:
        path = Path(__file__).parent.parent.parent / "config" / "topic_overrides.json"

    if not path.exists():
        _overrides_cache = {}
        return _overrides_cache

    with open(path) as f:
        raw = json.load(f)

    _overrides_cache = {}
    for market_id, topic_str in raw.items():
        try:
            _overrides_cache[market_id] = Topic(topic_str.lower())
        except ValueError:
            continue

    return _overrides_cache


def _get_group_prefix(event_ticker: str) -> str:
    """Map event_ticker to its group using longest-prefix matching.

    The upstream categories.py uses substring matching which can cause
    false positives (e.g., "EC" matching inside "FEDDECISION"). We use
    prefix matching on the alphabetic prefix of the event_ticker instead,
    trying longest patterns first.
    """
    # Extract the alphabetic prefix (before any dash or digit suffix)
    prefix = re.match(r"^([A-Za-z]+)", event_ticker)
    if not prefix:
        return "Other"

    alpha_prefix = prefix.group(1).upper()

    # Sort patterns by length descending so "FEDDECISION" matches before "FED"
    sorted_patterns = sorted(SUBCATEGORY_PATTERNS, key=lambda x: len(x[0]), reverse=True)

    for pattern, group, _, _ in sorted_patterns:
        if alpha_prefix.startswith(pattern) or pattern.startswith(alpha_prefix):
            # Exact prefix match: pattern is a prefix of alpha_prefix or vice versa
            if alpha_prefix == pattern or alpha_prefix.startswith(pattern):
                return group

    return "Other"


def classify_kalshi(
    event_ticker: str,
    ticker: str = "",
    title: str = "",
    overrides_path: Path | None = None,
) -> Topic:
    """Classify a Kalshi market into a Topic.

    Uses longest-prefix matching on event_ticker against the categories
    taxonomy, then maps the group to our Topic enum.

    Falls back to keyword matching on title if event_ticker is empty.
    """
    # Check overrides first
    overrides = _load_overrides(overrides_path)
    if ticker and ticker in overrides:
        return overrides[ticker]

    # Use prefix matching against categories taxonomy
    if event_ticker:
        group = _get_group_prefix(event_ticker)
        topic = _GROUP_TO_TOPIC.get(group, Topic.OTHER)
        if topic != Topic.OTHER:
            return topic

    # Fallback: keyword match on title
    if title:
        for pattern, topic in _POLYMARKET_PATTERNS:
            if pattern.search(title):
                return topic

    return Topic.OTHER


def classify_polymarket(
    question: str,
    slug: str = "",
    market_id: str = "",
    overrides_path: Path | None = None,
) -> Topic:
    """Classify a Polymarket market into a Topic.

    Uses keyword matching on the question text, with override support.
    """
    # Check overrides first
    overrides = _load_overrides(overrides_path)
    if market_id and market_id in overrides:
        return overrides[market_id]
    if slug and slug in overrides:
        return overrides[slug]

    # Keyword matching on question
    for pattern, topic in _POLYMARKET_PATTERNS:
        if pattern.search(question):
            return topic

    return Topic.OTHER


def clear_overrides_cache() -> None:
    """Clear the cached overrides (for testing)."""
    global _overrides_cache
    _overrides_cache = None
