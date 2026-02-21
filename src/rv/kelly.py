"""Kelly criterion position sizing for binary prediction market contracts.

Computes optimal bet size given edge, win probability, and bankroll,
with safety adjustments (fractional Kelly, hard caps).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionLimits:
    """Hard caps on position sizing."""

    max_per_contract: float = 500.0  # max dollars on any single contract
    max_per_topic: float = 2000.0  # max dollars deployed in one topic
    max_per_venue: float = 3000.0  # max dollars on one venue
    max_total: float = 5000.0  # max total portfolio exposure


def kelly_fraction(
    edge: float,
    win_prob: float,
    fraction: float = 0.5,
) -> float:
    """Compute fractional Kelly bet size as fraction of bankroll.

    For binary outcomes (pay $1 if win, lose cost if lose):
        b = (1 / price) - 1  (odds received)
        f* = (p * (b + 1) - 1) / b = (p - price) / (1 - price)

    where p = true win probability, price = cost of contract.

    Args:
        edge: Probability edge = true_prob - market_prob (can be negative)
        win_prob: Estimated true probability of the contract winning (0-1)
        fraction: Fractional Kelly multiplier (default: 0.5 = half-Kelly)

    Returns:
        Fraction of bankroll to bet (0 if no edge or negative edge).
    """
    if edge <= 0:
        return 0.0

    if win_prob <= 0 or win_prob >= 1:
        return 0.0

    # Market price = win_prob - edge would be the market's implied prob,
    # but we receive the contract at market price.
    # For a binary contract priced at `price`:
    #   If win: profit = 1 - price
    #   If lose: loss = price
    #   Odds b = (1 - price) / price
    # Kelly fraction f* = (p * b - q) / b = p - q/b = p - q*price/(1-price)
    # Simplified: f* = (p*(1-price) - (1-p)*price) / (1-price)
    #            = (p - price) / (1 - price)

    market_price = win_prob - edge
    if market_price <= 0 or market_price >= 1:
        return 0.0

    raw_kelly = (win_prob - market_price) / (1.0 - market_price)

    # Clamp to [0, 1] and apply fractional Kelly
    return max(0.0, min(1.0, raw_kelly)) * fraction


def size_position(
    edge: float,
    win_prob: float,
    bankroll: float,
    limits: PositionLimits | None = None,
    current_contract_exposure: float = 0.0,
    current_topic_exposure: float = 0.0,
    current_venue_exposure: float = 0.0,
    current_total_exposure: float = 0.0,
    fraction: float = 0.5,
) -> float:
    """Compute dollar position size with all caps applied.

    Args:
        edge: Probability edge (true_prob - market_prob)
        win_prob: Estimated true probability
        bankroll: Total bankroll in dollars
        limits: Position limit caps
        current_*_exposure: Existing exposure at each level
        fraction: Fractional Kelly multiplier

    Returns:
        Dollar amount to deploy (may be 0 if no edge or caps hit).
    """
    if limits is None:
        limits = PositionLimits()

    kf = kelly_fraction(edge, win_prob, fraction=fraction)
    if kf <= 0:
        return 0.0

    raw_size = kf * bankroll

    # Apply caps — take the minimum of all applicable limits
    remaining_contract = max(0.0, limits.max_per_contract - current_contract_exposure)
    remaining_topic = max(0.0, limits.max_per_topic - current_topic_exposure)
    remaining_venue = max(0.0, limits.max_per_venue - current_venue_exposure)
    remaining_total = max(0.0, limits.max_total - current_total_exposure)

    size = min(raw_size, remaining_contract, remaining_topic, remaining_venue, remaining_total)

    return max(0.0, size)
