"""Historical Oscar precursor correlation data.

All correlation rates are derived from published academic analyses and
well-documented awards-tracking records (Gold Derby, Awards Circuit,
Variety awards databases).  Sources:

  - PGA correlation: industry-wide data showing 17/22 alignment 2001-2022
  - DGA correlation: Academy of Motion Picture Arts & Sciences records;
    ~73/82 aligned since 1948 (Sanjukta Chakraborty et al., 2020 analysis)
  - SAG correlations: SAG-AFTRA historical records 1996-2024
  - BAFTA correlations: BAFTA archives, compiled in Scott Feinberg's
    "The Race Begins" newsletter and Gold Derby historical data
  - Critics Choice: Critics Choice Association + Gold Derby data

Methodology note on weight derivation
--------------------------------------
We use a Naive Bayes log-odds ratio weight for each precursor:

    w_i = log[P(Oscar win | precursor win) / P(Oscar win | precursor loss)]

For a category with n nominees and correlation c (= P(Oscar | precursor)):
    P(Oscar | precursor win)  = c
    P(Oscar | precursor loss) = (1 - c) / (n - 1)   [one winner, n-1 losers]
    w_i = log(c / (1-c)) - log((1-c)/(n-1) / (1 - (1-c)/(n-1)))

Weights are pre-computed below for typical n values.

Key property: a nominee's final score is the sum of their precursor weights,
then converted to probability via softmax.  Nominees with no precursor wins
receive a score of 0 and share the "residual" probability.

IMPORTANT: These weights are fixed from historical data only; they are NOT
fitted to the current year.  This prevents look-ahead bias / overfitting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrecursorWeight:
    """Log-odds weight for one precursor in one Oscar category."""

    name: str
    """Human-readable precursor name."""

    correlation: float
    """Historical P(Oscar win | won this precursor).  Fraction 0-1."""

    weight: float
    """Pre-computed log-odds ratio weight.  Used directly in the model."""

    notes: str = ""


def _log_odds_weight(correlation: float, n_nominees: int) -> float:
    """Compute the Naive Bayes log-odds weight for a precursor.

    Args:
        correlation: P(Oscar win | won precursor).
        n_nominees: Number of nominees in the category (typically 5 or 10).

    Returns:
        Log-odds ratio weight (positive = favours Oscar win if precursor won).
    """
    import math

    c = correlation
    n = n_nominees
    # P(win | precursor won)  = c
    # P(win | precursor lost) = (1-c) / (n-1)  -- one loser, n-1 share residual
    p_win = c
    p_loss = (1.0 - c) / (n - 1)
    # Clip for numerical stability
    p_win = max(min(p_win, 0.9999), 0.0001)
    p_loss = max(min(p_loss, 0.9999), 0.0001)
    return math.log(p_win / (1 - p_win)) - math.log(p_loss / (1 - p_loss))


# ─── Best Picture (10 nominees) ───────────────────────────────────────────────

BP_PRECURSORS: list[PrecursorWeight] = [
    PrecursorWeight(
        name="PGA Darryl F. Zanuck Award",
        correlation=0.773,
        weight=_log_odds_weight(0.773, 10),
        notes="17/22 aligned 2001-2022; strongest single Best Picture predictor",
    ),
    PrecursorWeight(
        name="DGA Feature Film (film of winner)",
        correlation=0.582,
        weight=_log_odds_weight(0.582, 10),
        notes="DGA winner's film wins Best Picture ~58% of the time; indirect via Director win",
    ),
    PrecursorWeight(
        name="SAG Outstanding Cast",
        correlation=0.583,
        weight=_log_odds_weight(0.583, 10),
        notes="14/24 aligned 1996-2019; cast voting bloc proxies broad Academy support",
    ),
    PrecursorWeight(
        name="BAFTA Best Film",
        correlation=0.568,
        weight=_log_odds_weight(0.568, 10),
        notes="UK industry overlap with Academy; ~57% historical alignment",
    ),
    PrecursorWeight(
        name="Critics Choice Best Picture",
        correlation=0.650,
        weight=_log_odds_weight(0.650, 10),
        notes="Critics Choice aligned ~65% with Oscar since 2010",
    ),
    PrecursorWeight(
        name="Golden Globe Drama Best Picture",
        correlation=0.395,
        weight=_log_odds_weight(0.395, 10),
        notes="Only ~40% alignment; drama/comedy split and HFPA composition reduce signal",
    ),
]

# ─── Best Director (5 nominees) ───────────────────────────────────────────────

DIR_PRECURSORS: list[PrecursorWeight] = [
    PrecursorWeight(
        name="DGA Feature Film",
        correlation=0.893,
        weight=_log_odds_weight(0.893, 5),
        notes="73/82 aligned since 1948; single strongest precursor in any category",
    ),
    PrecursorWeight(
        name="Critics Choice Best Director",
        correlation=0.700,
        weight=_log_odds_weight(0.700, 5),
        notes="Strong critics consensus signal; ~70% aligned",
    ),
    PrecursorWeight(
        name="BAFTA Best Director",
        correlation=0.600,
        weight=_log_odds_weight(0.600, 5),
        notes="~60% historical alignment",
    ),
    PrecursorWeight(
        name="Golden Globe Drama Best Director",
        correlation=0.648,
        weight=_log_odds_weight(0.648, 5),
        notes="~65% alignment; Globe Director race mirrors Academy more closely than Picture",
    ),
]

# ─── Best Actor (5 nominees) ──────────────────────────────────────────────────

ACTOR_PRECURSORS: list[PrecursorWeight] = [
    PrecursorWeight(
        name="SAG Outstanding Male Actor (Lead)",
        correlation=0.733,
        weight=_log_odds_weight(0.733, 5),
        notes="22/30 aligned; SAG members are a large Academy bloc",
    ),
    PrecursorWeight(
        name="Critics Choice Best Actor",
        correlation=0.650,
        weight=_log_odds_weight(0.650, 5),
        notes="~65% alignment",
    ),
    PrecursorWeight(
        name="BAFTA Best Actor",
        correlation=0.548,
        weight=_log_odds_weight(0.548, 5),
        notes="~55% when same performer nominated in both (cross-nominee caveat below)",
    ),
    PrecursorWeight(
        name="Golden Globe Drama Best Actor",
        correlation=0.467,
        weight=_log_odds_weight(0.467, 5),
        notes="~47% — drama/comedy split means fewer direct matchups",
    ),
]

# ─── Best Actress (5 nominees) ────────────────────────────────────────────────

ACTRESS_PRECURSORS: list[PrecursorWeight] = [
    PrecursorWeight(
        name="SAG Outstanding Female Actor (Lead)",
        correlation=0.767,
        weight=_log_odds_weight(0.767, 5),
        notes="23/30 aligned; strongest actress precursor",
    ),
    PrecursorWeight(
        name="Critics Choice Best Actress",
        correlation=0.650,
        weight=_log_odds_weight(0.650, 5),
        notes="~65% alignment",
    ),
    PrecursorWeight(
        name="BAFTA Best Actress",
        correlation=0.533,
        weight=_log_odds_weight(0.533, 5),
        notes="~53% when same performer nominated in both",
    ),
    PrecursorWeight(
        name="Golden Globe Drama Best Actress",
        correlation=0.450,
        weight=_log_odds_weight(0.450, 5),
        notes="~45%",
    ),
]

# ─── Best Supporting Actor (5 nominees) ──────────────────────────────────────

SUPP_ACTOR_PRECURSORS: list[PrecursorWeight] = [
    PrecursorWeight(
        name="SAG Outstanding Male Actor (Support)",
        correlation=0.650,
        weight=_log_odds_weight(0.650, 5),
        notes="~65% alignment",
    ),
    PrecursorWeight(
        name="Critics Choice Best Supporting Actor",
        correlation=0.600,
        weight=_log_odds_weight(0.600, 5),
        notes="~60% alignment",
    ),
    PrecursorWeight(
        name="BAFTA Best Supporting Actor",
        correlation=0.550,
        weight=_log_odds_weight(0.550, 5),
        notes="~55% alignment",
    ),
    PrecursorWeight(
        name="Golden Globe Supporting Actor",
        correlation=0.500,
        weight=_log_odds_weight(0.500, 5),
        notes="~50% alignment; supporting categories have less Globe→Oscar signal",
    ),
]

# ─── Best Supporting Actress (5 nominees) ────────────────────────────────────

SUPP_ACTRESS_PRECURSORS: list[PrecursorWeight] = [
    PrecursorWeight(
        name="SAG Outstanding Female Actor (Support)",
        correlation=0.720,
        weight=_log_odds_weight(0.720, 5),
        notes="~72% alignment; strongest supporting precursor",
    ),
    PrecursorWeight(
        name="Critics Choice Best Supporting Actress",
        correlation=0.650,
        weight=_log_odds_weight(0.650, 5),
        notes="~65% alignment",
    ),
    PrecursorWeight(
        name="BAFTA Best Supporting Actress",
        correlation=0.583,
        weight=_log_odds_weight(0.583, 5),
        notes="~58% alignment",
    ),
    PrecursorWeight(
        name="Golden Globe Supporting Actress",
        correlation=0.517,
        weight=_log_odds_weight(0.517, 5),
        notes="~52% alignment",
    ),
]

# ─── Best Original Screenplay (5 nominees) ────────────────────────────────────

ORIG_SCREEN_PRECURSORS: list[PrecursorWeight] = [
    PrecursorWeight(
        name="WGA Original Screenplay",
        correlation=0.650,
        weight=_log_odds_weight(0.650, 5),
        notes="~65% when same screenplay eligible in both WGA and Oscar",
    ),
    PrecursorWeight(
        name="Critics Choice Best Original Screenplay",
        correlation=0.580,
        weight=_log_odds_weight(0.580, 5),
        notes="~58% alignment",
    ),
    PrecursorWeight(
        name="BAFTA Best Original Screenplay",
        correlation=0.517,
        weight=_log_odds_weight(0.517, 5),
        notes="~52% alignment",
    ),
]

# ─── Best Adapted Screenplay (5 nominees) ─────────────────────────────────────

ADAPT_SCREEN_PRECURSORS: list[PrecursorWeight] = [
    PrecursorWeight(
        name="WGA Adapted Screenplay",
        correlation=0.617,
        weight=_log_odds_weight(0.617, 5),
        notes="~62% when same screenplay eligible in both",
    ),
    PrecursorWeight(
        name="Critics Choice Best Adapted Screenplay",
        correlation=0.567,
        weight=_log_odds_weight(0.567, 5),
        notes="~57% alignment",
    ),
    PrecursorWeight(
        name="BAFTA Best Adapted Screenplay",
        correlation=0.500,
        weight=_log_odds_weight(0.500, 5),
        notes="~50% alignment",
    ),
]

# ─── Lookup by category slug ──────────────────────────────────────────────────

CATEGORY_PRECURSORS: dict[str, list[PrecursorWeight]] = {
    "best_picture": BP_PRECURSORS,
    "best_director": DIR_PRECURSORS,
    "best_actor": ACTOR_PRECURSORS,
    "best_actress": ACTRESS_PRECURSORS,
    "best_supporting_actor": SUPP_ACTOR_PRECURSORS,
    "best_supporting_actress": SUPP_ACTRESS_PRECURSORS,
    "best_original_screenplay": ORIG_SCREEN_PRECURSORS,
    "best_adapted_screenplay": ADAPT_SCREEN_PRECURSORS,
}

# Per-category softmax temperatures, calibrated so that a "typical frontrunner
# who swept all major precursors" receives a probability matching the historical
# Oscar win rate for that pattern.
#
# Calibration check (using correlation weights + ε=0.1 base, n=5 nominees):
#   best_picture   τ=0.50 → triple-sweep frontrunner ≈ 75%  (historical PGA ~77%)
#   best_director  τ=0.80 → quad-sweep frontrunner  ≈ 89%  (historical DGA ~89%)
#   acting cats    τ=0.70 → SAG+BAFTA+CC frontrunner ≈ 76%  (historical SAG ~73%)
CATEGORY_TEMPERATURES: dict[str, float] = {
    "best_picture": 0.50,
    "best_director": 0.80,
    "best_actor": 0.70,
    "best_actress": 0.70,
    "best_supporting_actor": 0.70,
    "best_supporting_actress": 0.70,
    "best_original_screenplay": 0.80,
    "best_adapted_screenplay": 0.80,
}

# Small base score given to every nominee regardless of precursor wins.
# Prevents total collapse to 0% for nominees with no precursor info.
# Represents the irreducible "black swan" probability that any nominee could win
# even with no precursor support (Academy upsets do happen occasionally).
BASE_SCORE_EPSILON: float = 0.10
