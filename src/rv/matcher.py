"""Market matching and series detection for relative value analysis.

Cross-venue matching: pairs Kalshi ↔ Polymarket contracts on the same event.
Series detection: groups contracts into term structures or threshold series.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from src.rv.classifier import Topic
from src.rv.normalizer import NormalizedQuote


@dataclass
class MarketPair:
    """A cross-venue pair: same event on Kalshi and Polymarket."""

    kalshi: NormalizedQuote
    polymarket: NormalizedQuote
    match_confidence: str  # "high", "medium", "low"
    match_method: str  # "curated", "fuzzy"

    @property
    def cross_venue_spread(self) -> float:
        """Absolute difference in implied probability across venues."""
        return abs(self.kalshi.prob_mid - self.polymarket.prob_mid)


@dataclass
class ContractSeries:
    """A group of contracts forming a term structure or threshold series.

    Term structure: same event, different expiry dates.
        e.g., "Fed cuts ≥25bps by March/May/June"
    Threshold series: same metric, different thresholds.
        e.g., "CPI > 2.5%/3.0%/3.5%"
    """

    topic: Topic
    series_type: str  # "term_structure" or "threshold"
    contracts: list[NormalizedQuote] = field(default_factory=list)
    venue: str = ""  # "kalshi", "polymarket", or "cross"
    event_group: str = ""  # e.g., "FEDDECISION", "CPI"
    label: str = ""  # human-readable series name

    @property
    def size(self) -> int:
        return len(self.contracts)


# --- Cross-venue matching ---


def _load_curated_pairs(path: Path | None = None) -> dict[str, str]:
    """Load curated market pairings from JSON.

    Format: {"kalshi_ticker": "polymarket_id_or_slug", ...}
    """
    if path is None:
        path = Path(__file__).parent.parent.parent / "config" / "matched_pairs.json"

    if not path.exists():
        return {}

    with open(path) as f:
        return json.load(f)


def _title_similarity(a: str, b: str) -> float:
    """Compute normalized title similarity between two market titles."""

    # Normalize: lowercase, strip punctuation, collapse whitespace
    def _normalize(s: str) -> str:
        s = s.lower()
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0

    return SequenceMatcher(None, na, nb).ratio()


def _dates_compatible(k: NormalizedQuote, p: NormalizedQuote, tolerance_days: int = 3) -> bool:
    """Check if two contracts have compatible resolution dates."""
    if k.close_time is None or p.close_time is None:
        # Can't verify — allow match but it will be lower confidence
        return True

    # Make both timezone-naive for comparison
    kt = k.close_time.replace(tzinfo=None) if k.close_time.tzinfo else k.close_time
    pt = p.close_time.replace(tzinfo=None) if p.close_time.tzinfo else p.close_time

    delta = abs((kt - pt).days)
    return delta <= tolerance_days


def match_cross_venue(
    kalshi_quotes: list[NormalizedQuote],
    polymarket_quotes: list[NormalizedQuote],
    curated_pairs_path: Path | None = None,
    min_similarity: float = 0.75,
) -> list[MarketPair]:
    """Match Kalshi and Polymarket markets on the same event.

    Strategy (hybrid):
    1. Check curated pairs file first (high confidence)
    2. For remaining: match by same topic + compatible resolution date + title similarity

    Args:
        kalshi_quotes: Normalized Kalshi markets
        polymarket_quotes: Normalized Polymarket markets
        curated_pairs_path: Path to curated pairs JSON
        min_similarity: Minimum title similarity for fuzzy matching (0-1)

    Returns:
        List of matched market pairs
    """
    curated = _load_curated_pairs(curated_pairs_path)
    pairs: list[MarketPair] = []
    matched_poly_ids: set[str] = set()
    matched_kalshi_ids: set[str] = set()

    # Build lookup for Polymarket quotes
    poly_by_id: dict[str, NormalizedQuote] = {}
    poly_by_slug: dict[str, NormalizedQuote] = {}
    for pq in polymarket_quotes:
        poly_by_id[pq.market_id] = pq
        if pq.event_group:
            poly_by_slug[pq.event_group] = pq

    # Phase 1: Curated matches
    for kalshi_ticker, poly_key in curated.items():
        kq = next((k for k in kalshi_quotes if k.market_id == kalshi_ticker), None)
        pq = poly_by_id.get(poly_key) or poly_by_slug.get(poly_key)

        if kq and pq:
            pairs.append(
                MarketPair(
                    kalshi=kq,
                    polymarket=pq,
                    match_confidence="high",
                    match_method="curated",
                )
            )
            matched_kalshi_ids.add(kq.market_id)
            matched_poly_ids.add(pq.market_id)

    # Phase 2: Fuzzy matching on remaining
    unmatched_kalshi = [k for k in kalshi_quotes if k.market_id not in matched_kalshi_ids]
    unmatched_poly = [p for p in polymarket_quotes if p.market_id not in matched_poly_ids]

    for kq in unmatched_kalshi:
        if not kq.topic:
            continue

        best_match: NormalizedQuote | None = None
        best_score = 0.0

        for pq in unmatched_poly:
            if pq.market_id in matched_poly_ids:
                continue

            # Must be same topic
            if pq.topic != kq.topic:
                continue

            # Check date compatibility
            if not _dates_compatible(kq, pq):
                continue

            # Title similarity
            sim = _title_similarity(kq.title, pq.title)
            if sim > best_score and sim >= min_similarity:
                best_score = sim
                best_match = pq

        if best_match is not None:
            confidence = "high" if best_score >= 0.90 else "medium" if best_score >= 0.80 else "low"
            pairs.append(
                MarketPair(
                    kalshi=kq,
                    polymarket=best_match,
                    match_confidence=confidence,
                    match_method="fuzzy",
                )
            )
            matched_poly_ids.add(best_match.market_id)

    return pairs


# --- Series detection ---


def _extract_threshold(title: str) -> float | None:
    """Extract a numeric threshold from a contract title.

    Examples:
        "CPI above 3.0%"     → 3.0
        "Temperature above 80°F" → 80.0
        "Bitcoin above $100,000"  → 100000.0
    """
    # Pattern: "above/over/exceed/at least" + number
    patterns = [
        r"(?:above|over|exceed|at least|greater than|more than|≥|>=)\s*\$?([\d,]+\.?\d*)",
        r"(?:below|under|less than|at most|≤|<=)\s*\$?([\d,]+\.?\d*)",
        r"(?:between)\s*\$?([\d,]+\.?\d*)\s*(?:and|to|-)\s*\$?([\d,]+\.?\d*)",
        # "X or more" pattern
        r"\$?([\d,]+\.?\d*)\s*(?:or more|or higher|or above|\+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, title, re.I)
        if match:
            val_str = match.group(1).replace(",", "")
            try:
                return float(val_str)
            except ValueError:
                continue

    return None


def detect_series(
    quotes: list[NormalizedQuote],
    topic: Topic,
    min_series_size: int = 3,
) -> list[ContractSeries]:
    """Detect term structure and threshold series within a topic.

    Groups contracts by event_group (e.g., event_ticker for Kalshi)
    and analyzes whether they form a term structure (different dates)
    or threshold series (different numeric thresholds).

    Args:
        quotes: Normalized quotes, already filtered to one topic
        topic: The topic these quotes belong to
        min_series_size: Minimum contracts to form a series

    Returns:
        List of detected contract series
    """
    series_list: list[ContractSeries] = []

    # Group by event_group
    groups: dict[str, list[NormalizedQuote]] = {}
    for q in quotes:
        if q.event_group:
            groups.setdefault(q.event_group, []).append(q)

    for group_key, group_quotes in groups.items():
        if len(group_quotes) < min_series_size:
            continue

        # Try to detect term structure (contracts with different close dates)
        dated_quotes = [q for q in group_quotes if q.close_time is not None]
        if len(dated_quotes) >= min_series_size:
            # Check if dates are actually different (not all same day)
            unique_dates = {q.close_time.date() for q in dated_quotes if q.close_time}  # type: ignore[union-attr]
            if len(unique_dates) >= min_series_size:
                # Sort by close date
                dated_quotes.sort(key=lambda q: q.close_time or datetime_min())
                series_list.append(
                    ContractSeries(
                        topic=topic,
                        series_type="term_structure",
                        contracts=dated_quotes,
                        venue=dated_quotes[0].venue,
                        event_group=group_key,
                        label=f"{group_key} term structure",
                    )
                )
                continue  # don't also try threshold for same group

        # Try to detect threshold series (contracts with different numeric thresholds)
        threshold_quotes: list[tuple[float, NormalizedQuote]] = []
        for q in group_quotes:
            threshold = _extract_threshold(q.title)
            if threshold is not None:
                threshold_quotes.append((threshold, q))

        if len(threshold_quotes) >= min_series_size:
            # Sort by threshold value
            threshold_quotes.sort(key=lambda x: x[0])
            sorted_quotes = [q for _, q in threshold_quotes]
            series_list.append(
                ContractSeries(
                    topic=topic,
                    series_type="threshold",
                    contracts=sorted_quotes,
                    venue=sorted_quotes[0].venue,
                    event_group=group_key,
                    label=f"{group_key} threshold series",
                )
            )

    return series_list


def datetime_min():
    """Return a minimal datetime for sorting purposes."""
    from datetime import datetime

    return datetime.min
