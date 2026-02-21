"""Edge calculation for prediction market relative value trades.

Computes edge magnitude, direction, and spread-adjusted metrics for:
- Cross-venue arbitrage (Kalshi vs Polymarket)
- Term structure violations (monotonicity breaks)
- Threshold/CDF inconsistencies (fitted distribution residuals)
- Model-vs-market deviations (external reference model)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.rv.classifier import Topic
from src.rv.kelly import kelly_fraction
from src.rv.liquidity import grade_liquidity
from src.rv.matcher import ContractSeries, MarketPair, _extract_threshold
from src.rv.normalizer import NormalizedQuote


@dataclass
class Edge:
    """A detected mispricing opportunity."""

    edge_type: str  # "cross_venue", "term_structure", "threshold_cdf", "model_vs_market"
    topic: Topic
    magnitude_pp: float  # edge in probability points (e.g., 5.0 = 5pp)
    spread_ratio: float  # magnitude / average_spread (how many spreads is the edge?)
    direction: str  # human-readable direction (e.g., "buy Kalshi @ 0.45, sell Poly @ 0.52")
    contracts: list[NormalizedQuote] = field(default_factory=list)
    liquidity_grade: str = "C"
    kelly_frac: float = 0.0  # suggested bankroll fraction
    kelly_size_usd: float = 0.0  # dollar amount at given bankroll
    metadata: dict = field(default_factory=dict)  # extra info (fitted params, etc.)


def _average_spread(quotes: list[NormalizedQuote]) -> float:
    """Compute average spread across quotes that have bid/ask data."""
    spreads = [q.spread for q in quotes if q.spread is not None and q.spread > 0]
    if not spreads:
        return 0.05  # default 5 cent spread assumption when no data
    return sum(spreads) / len(spreads)


def compute_cross_venue_edge(
    pair: MarketPair,
    bankroll: float = 10000.0,
    kelly_mult: float = 0.5,
) -> Edge | None:
    """Compute edge for a cross-venue matched pair.

    Edge = abs(kalshi_mid - polymarket_mid), adjusted for spreads.
    Direction: buy the cheaper venue, sell the more expensive.
    """
    k_prob = pair.kalshi.prob_mid_or_last
    p_prob = pair.polymarket.prob_mid_or_last
    raw_edge = abs(k_prob - p_prob)

    if raw_edge < 0.005:  # less than 0.5pp — not meaningful
        return None

    # Spread-adjusted edge: deduct half-spread on each side
    k_half_spread = (pair.kalshi.spread or 0.05) / 2.0
    p_half_spread = (pair.polymarket.spread or 0.05) / 2.0
    adjusted_edge = raw_edge - k_half_spread - p_half_spread

    if adjusted_edge <= 0:
        return None

    avg_spread = _average_spread([pair.kalshi, pair.polymarket])
    spread_ratio = adjusted_edge / avg_spread if avg_spread > 0 else 0.0

    # Direction: buy cheap, sell expensive
    if k_prob < p_prob:
        direction = f"buy Kalshi @ {k_prob:.2f}, sell Poly @ {p_prob:.2f}"
        win_prob = p_prob  # we think the higher price is more accurate
    else:
        direction = f"buy Poly @ {p_prob:.2f}, sell Kalshi @ {k_prob:.2f}"
        win_prob = k_prob

    # Kelly sizing
    kf = kelly_fraction(adjusted_edge, win_prob, fraction=kelly_mult)
    kelly_usd = kf * bankroll

    # Liquidity: use the worse of the two grades
    k_grade = grade_liquidity(pair.kalshi)
    p_grade = grade_liquidity(pair.polymarket)
    worst_grade = max(k_grade, p_grade)  # 'C' > 'B' > 'A' alphabetically = worst

    return Edge(
        edge_type="cross_venue",
        topic=Topic(pair.kalshi.topic) if pair.kalshi.topic else Topic.OTHER,
        magnitude_pp=adjusted_edge * 100,  # convert to percentage points
        spread_ratio=spread_ratio,
        direction=direction,
        contracts=[pair.kalshi, pair.polymarket],
        liquidity_grade=worst_grade,
        kelly_frac=kf,
        kelly_size_usd=kelly_usd,
        metadata={
            "raw_edge_pp": raw_edge * 100,
            "kalshi_mid": k_prob,
            "polymarket_mid": p_prob,
        },
    )


def compute_term_structure_edges(
    series: ContractSeries,
    bankroll: float = 10000.0,
    kelly_mult: float = 0.5,
) -> list[Edge]:
    """Find monotonicity violations in a term structure series.

    For a proper term structure (e.g., "Fed cuts by March/May/June"),
    P(event by later date) >= P(event by earlier date). Any violation
    is a calendar spread opportunity.
    """
    if series.series_type != "term_structure" or len(series.contracts) < 2:
        return []

    edges: list[Edge] = []
    avg_spread = _average_spread(series.contracts)

    for i in range(len(series.contracts) - 1):
        earlier = series.contracts[i]
        later = series.contracts[i + 1]

        p_earlier = earlier.prob_mid_or_last
        p_later = later.prob_mid_or_last

        # Violation: later date should have >= probability
        if p_earlier > p_later:
            violation_size = p_earlier - p_later
            spread_ratio = violation_size / avg_spread if avg_spread > 0 else 0.0

            # Minimum threshold for noise rejection
            if violation_size < 0.01:
                continue

            # Direction: buy later (underpriced), sell earlier (overpriced)
            direction = f"buy {later.market_id} @ {p_later:.2f}, sell {earlier.market_id} @ {p_earlier:.2f}"

            win_prob = (p_earlier + p_later) / 2.0
            kf = kelly_fraction(violation_size, win_prob, fraction=kelly_mult)

            edges.append(
                Edge(
                    edge_type="term_structure",
                    topic=series.topic,
                    magnitude_pp=violation_size * 100,
                    spread_ratio=spread_ratio,
                    direction=direction,
                    contracts=[earlier, later],
                    liquidity_grade=max(grade_liquidity(earlier), grade_liquidity(later)),
                    kelly_frac=kf,
                    kelly_size_usd=kf * bankroll,
                    metadata={
                        "earlier_date": str(earlier.close_time),
                        "later_date": str(later.close_time),
                        "earlier_prob": p_earlier,
                        "later_prob": p_later,
                    },
                )
            )

    return edges


def compute_threshold_edges(
    series: ContractSeries,
    bankroll: float = 10000.0,
    kelly_mult: float = 0.5,
) -> list[Edge]:
    """Fit a parametric distribution to implied CDF and find residuals.

    For threshold series (e.g., "CPI > 2.5/3.0/3.5%"), the implied
    probabilities define an empirical CDF. Fit a normal distribution
    and flag contracts that deviate significantly from the fitted curve.
    """
    if series.series_type != "threshold" or len(series.contracts) < 3:
        return []

    # Extract (threshold, probability) pairs
    points: list[tuple[float, float, NormalizedQuote]] = []
    for q in series.contracts:
        threshold = _extract_threshold(q.title)
        if threshold is not None:
            points.append((threshold, q.prob_mid_or_last, q))

    if len(points) < 3:
        return []

    points.sort(key=lambda x: x[0])

    thresholds = np.array([p[0] for p in points])
    probs = np.array([p[1] for p in points])

    # These are P(X > threshold) = 1 - CDF(threshold)
    # So CDF(threshold) = 1 - prob
    cdf_values = 1.0 - probs

    # Fit a normal distribution: CDF(x) = Φ((x - μ) / σ)
    # Use least squares to find μ, σ
    from scipy.optimize import curve_fit
    from scipy.stats import norm

    def normal_cdf(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
        return norm.cdf(x, loc=mu, scale=sigma)

    try:
        # Initial guess: mean and std of thresholds
        p0 = [float(np.mean(thresholds)), float(np.std(thresholds)) or 1.0]
        popt, _ = curve_fit(normal_cdf, thresholds, cdf_values, p0=p0, maxfev=5000)
        fitted_mu, fitted_sigma = popt

        if fitted_sigma <= 0:
            return []

    except (RuntimeError, ValueError):
        # Curve fit failed — can't compute threshold edges
        return []

    # Compute residuals for each contract
    fitted_cdf = normal_cdf(thresholds, fitted_mu, fitted_sigma)
    fitted_probs = 1.0 - fitted_cdf  # back to P(X > threshold)
    residuals = probs - fitted_probs  # positive = market overprices probability

    avg_spread = _average_spread([p[2] for p in points])
    edges: list[Edge] = []

    for i, (threshold, market_prob, quote) in enumerate(points):
        residual = float(residuals[i])
        abs_residual = abs(residual)

        # Only flag if residual > 2pp
        if abs_residual < 0.02:
            continue

        spread_ratio = abs_residual / avg_spread if avg_spread > 0 else 0.0

        if residual > 0:
            direction = f"sell {quote.market_id} @ {market_prob:.2f} (overpriced vs fitted {fitted_probs[i]:.2f})"
        else:
            direction = f"buy {quote.market_id} @ {market_prob:.2f} (underpriced vs fitted {fitted_probs[i]:.2f})"

        # For Kelly: the "true" probability is the fitted value
        true_prob = float(fitted_probs[i])
        edge_for_kelly = abs_residual
        kf = kelly_fraction(edge_for_kelly, true_prob, fraction=kelly_mult)

        edges.append(
            Edge(
                edge_type="threshold_cdf",
                topic=series.topic,
                magnitude_pp=abs_residual * 100,
                spread_ratio=spread_ratio,
                direction=direction,
                contracts=[quote],
                liquidity_grade=grade_liquidity(quote),
                kelly_frac=kf,
                kelly_size_usd=kf * bankroll,
                metadata={
                    "threshold": threshold,
                    "market_prob": market_prob,
                    "fitted_prob": float(fitted_probs[i]),
                    "residual": residual,
                    "fitted_mu": fitted_mu,
                    "fitted_sigma": fitted_sigma,
                },
            )
        )

    return edges


def compute_model_edge(
    quote: NormalizedQuote,
    model_probability: float,
    bankroll: float = 10000.0,
    kelly_mult: float = 0.5,
) -> Edge | None:
    """Compute edge between an external model and market price.

    Used for NWS weather forecasts, CME FedWatch probs, Vegas odds.
    """
    market_prob = quote.prob_mid_or_last
    raw_edge = abs(model_probability - market_prob)

    if raw_edge < 0.01:  # less than 1pp
        return None

    # Spread-adjusted
    half_spread = (quote.spread or 0.05) / 2.0
    adjusted_edge = raw_edge - half_spread

    if adjusted_edge <= 0:
        return None

    spread_ratio = adjusted_edge / (quote.spread or 0.05) if (quote.spread or 0.05) > 0 else 0.0

    if model_probability > market_prob:
        direction = f"buy {quote.market_id} @ {market_prob:.2f} (model says {model_probability:.2f})"
    else:
        direction = f"sell {quote.market_id} @ {market_prob:.2f} (model says {model_probability:.2f})"

    kf = kelly_fraction(adjusted_edge, model_probability, fraction=kelly_mult)

    return Edge(
        edge_type="model_vs_market",
        topic=Topic(quote.topic) if quote.topic else Topic.OTHER,
        magnitude_pp=adjusted_edge * 100,
        spread_ratio=spread_ratio,
        direction=direction,
        contracts=[quote],
        liquidity_grade=grade_liquidity(quote),
        kelly_frac=kf,
        kelly_size_usd=kf * bankroll,
        metadata={
            "model_prob": model_probability,
            "market_prob": market_prob,
            "raw_edge_pp": raw_edge * 100,
        },
    )
