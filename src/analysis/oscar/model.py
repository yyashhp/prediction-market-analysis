"""Oscar prediction model.

Architecture: Precursor-correlation scoring + per-category softmax calibration.

For each nominee in a category:
  1. Compute a raw score = ε (base) + sum of precursor correlations for each won precursor
     (correlation ∈ [0,1]; using correlation rather than log-odds keeps scores in a range
      where softmax remains well-behaved across all category temperature settings)
  2. Convert scores to probabilities via softmax with per-category temperature τ
     (τ calibrated so that a "typical frontrunner who swept all major precursors"
      receives a probability matching the historical Oscar win rate for that pattern)
  3. Report model probability, Kalshi price, edge, and Kelly size

Why Naive Bayes log-odds and NOT a complex ML model:
  - Only ~5 data points per year (nominees); ~25 years = ~125 rows per category
  - Complex models (gradient boosting, neural nets) will overfit with high variance
  - The key information is already encoded in the precursor correlation weights,
    which are derived from the full historical record
  - Softmax temperature τ is the single calibration parameter, set by
    leave-one-year-out cross-validation on historical consensus accuracy
  - This approach is interpretable: the analyst can see WHICH precursors drive
    each probability estimate and reason about it

Model caveats (be explicit about limitations):
  - PGA and SAG results are not yet available (as of 2026-02-26); those
    weights show up as 0 for all nominees → probabilities are under-determined
    in categories where PGA/SAG are key predictors
  - BAFTA cross-nomination caveat for Best Actor (BAFTA winner not in Oscar
    field); the weight is voided this year for that category
  - This model does NOT incorporate film quality, cultural moment, or
    voter demographics — factors that occasionally override precursors
  - Treat model output as a calibrated prior, not a point prediction
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.analysis.oscar.historical_data import (
    BASE_SCORE_EPSILON,
    CATEGORY_PRECURSORS,
    CATEGORY_TEMPERATURES,
    PrecursorWeight,
)
from src.analysis.oscar.nominees_2026 import Nominee


@dataclass
class PredictionResult:
    """Model output for a single nominee."""

    nominee: str
    film: str
    model_prob: float           # Model probability 0–1
    kalshi_price: float | None  # Market price 0–1 (or None)
    gold_derby_prob: float | None  # Expert consensus 0–1 (or None)

    # Edge metrics
    edge_vs_market: float | None = None  # model - market (positive = take Yes)
    edge_vs_consensus: float | None = None  # model - gold derby

    # Precursors won (for interpretability)
    precursors_won: list[str] = field(default_factory=list)
    raw_score: float = 0.0
    notes: str = ""

    @property
    def kalshi_price_cents(self) -> int | None:
        if self.kalshi_price is None:
            return None
        return round(self.kalshi_price * 100)

    @property
    def kelly_fraction(self) -> float | None:
        """Half-Kelly fraction for this bet (if positive edge vs market)."""
        if self.kalshi_price is None or self.edge_vs_market is None:
            return None
        if self.edge_vs_market <= 0:
            return None
        p = self.model_prob
        q = self.kalshi_price
        # Kelly criterion for binary bet: f = (p - q) / (1 - q)
        if q >= 1.0:
            return None
        raw_kelly = (p - q) / (1.0 - q)
        return max(0.0, raw_kelly * 0.5)  # half-Kelly


@dataclass
class CategoryPrediction:
    """All predictions for one Oscar category."""

    category_slug: str
    category_display: str
    nominees: list[PredictionResult]
    temperature: float
    pending_precursors: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def top_pick(self) -> PredictionResult:
        return max(self.nominees, key=lambda n: n.model_prob)

    @property
    def best_edge_opportunity(self) -> PredictionResult | None:
        """Nominee with the highest positive edge vs Kalshi."""
        with_market = [n for n in self.nominees if n.edge_vs_market is not None]
        if not with_market:
            return None
        return max(with_market, key=lambda n: n.edge_vs_market or 0.0)


# Temperature parameter: controls how confident the model is.
# τ = 1.0: raw log-odds scores
# τ < 1.0: more conservative (spreads out probabilities)
# τ > 1.0: more decisive (concentrates on leader)
# Calibrated from historical analysis: when leader sweeps precursors,
# historical win rate is ~82% → τ adjusted to match
_DEFAULT_TEMPERATURE = 0.85


def _softmax(scores: list[float], temperature: float) -> list[float]:
    """Temperature-scaled softmax over scores."""
    scaled = [s / temperature for s in scores]
    max_s = max(scaled)
    exps = [math.exp(s - max_s) for s in scaled]  # subtract max for numerical stability
    total = sum(exps)
    return [e / total for e in exps]


def predict_category(
    category_slug: str,
    nominees: list[Nominee],
    temperature: float = _DEFAULT_TEMPERATURE,
) -> CategoryPrediction:
    """Run the prediction model for one Oscar category.

    Args:
        category_slug: Key into CATEGORY_PRECURSORS (e.g., "best_picture").
        nominees: List of Nominee objects for this year.
        temperature: Softmax temperature (lower = less decisive).

    Returns:
        CategoryPrediction with model probabilities, market comparison, edge.
    """
    from src.analysis.oscar.nominees_2026 import CATEGORY_DISPLAY

    precursor_weights: list[PrecursorWeight] = CATEGORY_PRECURSORS.get(category_slug, [])
    # Use correlation (0–1 range) rather than log-odds weights to prevent softmax collapse.
    # A nominee's raw score = ε (base) + sum of correlation values for precursors won.
    correlation_map: dict[str, float] = {p.name: p.correlation for p in precursor_weights}

    # Use per-category calibrated temperature (falls back to default if unknown slug)
    temperature = CATEGORY_TEMPERATURES.get(category_slug, temperature)

    # Calculate raw score for each nominee
    raw_scores: list[float] = []
    for nominee in nominees:
        score = BASE_SCORE_EPSILON + sum(correlation_map.get(p, 0.0) for p in nominee.precursors_won)
        raw_scores.append(score)

    probs = _softmax(raw_scores, temperature)

    # Build results
    results: list[PredictionResult] = []
    for nominee, prob, raw in zip(nominees, probs, raw_scores):
        market_price = nominee.kalshi_price_cents / 100.0 if nominee.kalshi_price_cents is not None else None
        gd_prob = nominee.gold_derby_pct / 100.0 if nominee.gold_derby_pct is not None else None

        edge_market = (prob - market_price) if market_price is not None else None
        edge_gd = (prob - gd_prob) if gd_prob is not None else None

        results.append(
            PredictionResult(
                nominee=nominee.name,
                film=nominee.film,
                model_prob=round(prob, 4),
                kalshi_price=market_price,
                gold_derby_prob=gd_prob,
                edge_vs_market=round(edge_market, 4) if edge_market is not None else None,
                edge_vs_consensus=round(edge_gd, 4) if edge_gd is not None else None,
                precursors_won=nominee.precursors_won,
                raw_score=round(raw, 3),
                notes=nominee.notes,
            )
        )

    # Identify pending precursors (those with non-zero weights not yet assigned to anyone)
    won_precursors: set[str] = set()
    for nominee in nominees:
        won_precursors.update(nominee.precursors_won)
    pending = [p.name for p in precursor_weights if p.name not in won_precursors]

    return CategoryPrediction(
        category_slug=category_slug,
        category_display=CATEGORY_DISPLAY.get(category_slug, category_slug),
        nominees=sorted(results, key=lambda r: r.model_prob, reverse=True),
        temperature=temperature,
        pending_precursors=pending,
    )


def run_all_categories() -> dict[str, CategoryPrediction]:
    """Run the model for all 2026 Oscar categories.

    Returns dict keyed by category slug.
    Per-category temperatures are applied automatically from CATEGORY_TEMPERATURES.
    """
    from src.analysis.oscar.nominees_2026 import CATEGORIES_2026

    return {slug: predict_category(slug, nominees) for slug, nominees in CATEGORIES_2026.items()}


def kelly_bet_size(result: PredictionResult, bankroll: float = 10_000.0) -> float | None:
    """Dollar amount to bet based on half-Kelly criterion.

    Returns None if no positive edge.
    """
    kf = result.kelly_fraction
    if kf is None:
        return None
    return round(bankroll * kf, 2)
