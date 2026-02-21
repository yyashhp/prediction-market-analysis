"""Liquidity assessment and filtering for prediction market contracts.

Applies configurable thresholds to filter out illiquid contracts
that would be unprofitable or risky to trade.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.rv.normalizer import NormalizedQuote


@dataclass
class LiquidityFilter:
    """Configurable liquidity thresholds."""

    min_volume_24h: float = 500.0  # minimum $500 daily volume
    max_spread: float = 0.10  # maximum 10 cent (10pp) spread
    min_open_interest: int = 200  # minimum 200 contracts outstanding


def grade_liquidity(
    quote: NormalizedQuote,
) -> str:
    """Assign a liquidity grade to a contract.

    Returns:
        'A' — liquid: tight spread, good volume, deep OI
        'B' — adequate: meets minimum thresholds but not great
        'C' — illiquid: below one or more minimum thresholds
    """
    score = 0

    # Spread scoring
    if quote.spread is not None:
        if quote.spread <= 0.03:
            score += 3  # very tight
        elif quote.spread <= 0.06:
            score += 2  # reasonable
        elif quote.spread <= 0.10:
            score += 1  # wide but tradable
        # else: 0 (too wide)

    # Volume scoring
    if quote.volume_24h >= 5000:
        score += 3
    elif quote.volume_24h >= 1000:
        score += 2
    elif quote.volume_24h >= 500:
        score += 1

    # OI scoring
    if quote.open_interest >= 2000:
        score += 3
    elif quote.open_interest >= 500:
        score += 2
    elif quote.open_interest >= 200:
        score += 1

    if score >= 7:
        return "A"
    elif score >= 4:
        return "B"
    else:
        return "C"


def passes_filter(
    quote: NormalizedQuote,
    filters: LiquidityFilter | None = None,
) -> bool:
    """Check if a contract meets minimum liquidity thresholds.

    All conditions must be met (AND logic). If a metric is unavailable
    (e.g. spread is None because no bid/ask), that condition is skipped
    rather than failing — avoids false negatives from missing data.
    """
    if filters is None:
        filters = LiquidityFilter()

    # Volume check
    if quote.volume_24h < filters.min_volume_24h:
        # Allow contracts where 24h volume isn't reported (e.g. Polymarket)
        # but total volume is significant
        if quote.volume_24h > 0:
            return False
        # If volume_24h is 0 and total_volume is also low, filter out
        if quote.total_volume < filters.min_volume_24h:
            return False

    # Spread check (skip if no bid/ask data)
    if quote.spread is not None and quote.spread > filters.max_spread:
        return False

    # Open interest check (skip if not available)
    if quote.open_interest > 0 and quote.open_interest < filters.min_open_interest:
        return False

    return True
