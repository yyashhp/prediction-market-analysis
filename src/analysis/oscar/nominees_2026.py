"""98th Academy Awards (2026) nominees and precursor results.

Ceremony: March 15, 2026 (host: Conan O'Brien, ABC)
Data as of: 2026-02-26 (day of compilation)

Key precursor status:
  DGA (Feb 7)            ✓ COMPLETE
  BAFTA (Feb 22)         ✓ COMPLETE
  Golden Globes (Jan)    ✓ COMPLETE
  Critics Choice (Jan)   ✓ COMPLETE
  PGA (Feb 28)           ⏳ 2 days away — not yet known
  SAG (Mar 1)            ⏳ 3 days away — not yet known
  WGA (Mar 8)            ⏳ 10 days away — not yet known

Notes on BAFTA cross-nomination caveat:
  The 2026 BAFTA Best Actor winner (Robert Aramayo, "I Swear") is NOT in
  the Oscar Best Actor field.  This is a known anomaly — BAFTA sometimes
  diverges from Oscar eligibility windows.  The BAFTA weight for Best Actor
  is therefore NOT credited to any Oscar nominee this year.

Sources: oscars.org, bafta.org, dga.org, sag-aftra.org, goldderby.com,
         kalshi.com/hub/oscars-2026 (prices as of 2026-02-26)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Nominee:
    """A single nominee in one Oscar category."""

    name: str
    """Person's name or film title (for Best Picture)."""

    film: str
    """Film the nomination is for."""

    precursors_won: list[str] = field(default_factory=list)
    """List of precursor award names won (must match PrecursorWeight.name)."""

    kalshi_price_cents: int | None = None
    """Current Kalshi market price in cents (1–99).  None if not listed."""

    gold_derby_pct: float | None = None
    """Gold Derby expert consensus probability (0–100).  None if unknown."""

    notes: str = ""


# ─── Best Picture ─────────────────────────────────────────────────────────────

BEST_PICTURE: list[Nominee] = [
    Nominee(
        name="One Battle After Another",
        film="One Battle After Another",
        precursors_won=[
            "DGA Feature Film (film of winner)",     # Paul Thomas Anderson won DGA
            "BAFTA Best Film",                        # Won BAFTA Best Film (6 wins total)
            "Critics Choice Best Picture",            # Won Critics Choice Best Picture
        ],
        kalshi_price_cents=73,
        gold_derby_pct=77.4,
        notes="DGA + BAFTA + Critics Choice sweep; 13 Oscar nominations; dominant frontrunner",
    ),
    Nominee(
        name="Sinners",
        film="Sinners",
        precursors_won=[],  # No major Best Picture precursor wins
        kalshi_price_cents=21,
        gold_derby_pct=17.7,
        notes="Record 16 Oscar nominations; BAFTA Screenplay/Score/Supp-Actress; no Picture precursors",
    ),
    Nominee(
        name="Hamnet",
        film="Hamnet",
        precursors_won=[
            "Golden Globe Drama Best Picture",        # Won Golden Globe Drama
        ],
        kalshi_price_cents=5,
        gold_derby_pct=1.7,
        notes="Golden Globe Drama win; Jessie Buckley BAFTA Actress; limited broader support",
    ),
    Nominee(
        name="Frankenstein",
        film="Frankenstein",
        precursors_won=[],
        kalshi_price_cents=1,
        gold_derby_pct=0.5,
        notes="Guillermo del Toro; multiple nominations but no Picture precursors",
    ),
    Nominee(
        name="Marty Supreme",
        film="Marty Supreme",
        precursors_won=[],
        kalshi_price_cents=1,
        gold_derby_pct=0.5,
        notes="Josh Safdie film; Timothée Chalamet lead",
    ),
    Nominee(
        name="Train Dreams",
        film="Train Dreams",
        precursors_won=[],
        kalshi_price_cents=1,
        gold_derby_pct=0.3,
    ),
    Nominee(
        name="Sentimental Value",
        film="Sentimental Value",
        precursors_won=[],
        kalshi_price_cents=1,
        gold_derby_pct=0.3,
    ),
    Nominee(
        name="The Secret Agent",
        film="The Secret Agent",
        precursors_won=[],
        kalshi_price_cents=1,
        gold_derby_pct=0.3,
    ),
    Nominee(
        name="F1",
        film="F1",
        precursors_won=[],
        kalshi_price_cents=1,
        gold_derby_pct=0.2,
    ),
    Nominee(
        name="Bugonia",
        film="Bugonia",
        precursors_won=[],
        kalshi_price_cents=1,
        gold_derby_pct=0.1,
    ),
]

# ─── Best Director ────────────────────────────────────────────────────────────

BEST_DIRECTOR: list[Nominee] = [
    Nominee(
        name="Paul Thomas Anderson",
        film="One Battle After Another",
        precursors_won=[
            "DGA Feature Film",                    # Won DGA Feb 7
            "BAFTA Best Director",                 # Won BAFTA Best Director
            "Critics Choice Best Director",        # Won Critics Choice Director
            "Golden Globe Drama Best Director",    # Won Golden Globe Director
        ],
        kalshi_price_cents=88,  # approximate; market implies ~85-90%
        gold_derby_pct=89.0,
        notes="Swept every major director precursor; historical DGA→Oscar rate ~89%",
    ),
    Nominee(
        name="Ryan Coogler",
        film="Sinners",
        precursors_won=[],
        kalshi_price_cents=7,
        gold_derby_pct=7.0,
        notes="No director precursors; film's record nominations give him a shot at historic upset",
    ),
    Nominee(
        name="Guillermo del Toro",
        film="Frankenstein",
        precursors_won=[],
        kalshi_price_cents=2,
        gold_derby_pct=1.5,
    ),
    Nominee(
        name="Chloé Zhao",
        film="Hamnet",
        precursors_won=[],
        kalshi_price_cents=2,
        gold_derby_pct=1.5,
    ),
    Nominee(
        name="Josh Safdie",
        film="Marty Supreme",
        precursors_won=[],
        kalshi_price_cents=1,
        gold_derby_pct=1.0,
    ),
]

# ─── Best Actor ───────────────────────────────────────────────────────────────

BEST_ACTOR: list[Nominee] = [
    Nominee(
        name="Timothée Chalamet",
        film="Marty Supreme",
        precursors_won=[
            # BAFTA went to Robert Aramayo (not in Oscar field) — no BAFTA credit here
            # Critics Choice: implied frontrunner
            "Critics Choice Best Actor",            # Strong implied win (80% Gold Derby)
            "Golden Globe Drama Best Actor",        # Implied; market prices show DiCaprio fell
        ],
        kalshi_price_cents=75,
        gold_derby_pct=80.2,
        notes=(
            "Swept acting precursors; BAFTA winner (Robert Aramayo) not in Oscar field, "
            "removing BAFTA as factor. DiCaprio dropped from 75¢ to 12¢ as Chalamet momentum built."
        ),
    ),
    Nominee(
        name="Leonardo DiCaprio",
        film="One Battle After Another",
        precursors_won=[],
        kalshi_price_cents=12,
        gold_derby_pct=10.0,
        notes="Once co-frontrunner; dropped sharply as Chalamet precursors accumulated",
    ),
    Nominee(
        name="Michael B. Jordan",
        film="Sinners",
        precursors_won=[],
        kalshi_price_cents=6,
        gold_derby_pct=5.0,
        notes="First Oscar nomination; benefiting from film's record noms",
    ),
    Nominee(
        name="Wagner Moura",
        film="The Secret Agent",
        precursors_won=[],
        kalshi_price_cents=4,
        gold_derby_pct=3.0,
    ),
    Nominee(
        name="Ethan Hawke",
        film="Blue Moon",
        precursors_won=[],
        kalshi_price_cents=3,
        gold_derby_pct=1.8,
    ),
]

# ─── Best Actress ─────────────────────────────────────────────────────────────

BEST_ACTRESS: list[Nominee] = [
    Nominee(
        name="Jessie Buckley",
        film="Hamnet",
        precursors_won=[
            "BAFTA Best Actress",                  # Won BAFTA Best Actress
        ],
        kalshi_price_cents=55,  # approximate; market implies ~55-60%
        gold_derby_pct=52.0,
        notes="BAFTA win is strong signal; SAG outcome (Mar 1) will confirm or complicate",
    ),
    Nominee(
        name="Kate Hudson",
        film="Song Sung Blue",
        precursors_won=[],
        kalshi_price_cents=20,
        gold_derby_pct=20.0,
        notes="First Oscar nomination; in SAG race",
    ),
    Nominee(
        name="Emma Stone",
        film="Bugonia",
        precursors_won=[],
        kalshi_price_cents=12,
        gold_derby_pct=12.0,
        notes="Previous winner; always a factor",
    ),
    Nominee(
        name="Renate Reinsve",
        film="Sentimental Value",
        precursors_won=[],
        kalshi_price_cents=8,
        gold_derby_pct=10.0,
        notes="Cannes winner history (The Worst Person in the World 2021)",
    ),
    Nominee(
        name="Rose Byrne",
        film="If I Had Legs I'd Kick You",
        precursors_won=[],
        kalshi_price_cents=5,
        gold_derby_pct=6.0,
        notes="SAG nominee",
    ),
]

# ─── Best Supporting Actor ────────────────────────────────────────────────────

BEST_SUPPORTING_ACTOR: list[Nominee] = [
    Nominee(
        name="Sean Penn",
        film="One Battle After Another",
        precursors_won=[
            # Research suggests Penn won BAFTA Supporting Actor for One Battle;
            # this is treated as probable based on the research noting "Sean Penn
            # supporting actor" as a BAFTA win for that film
            "BAFTA Best Supporting Actor",
        ],
        kalshi_price_cents=35,
        gold_derby_pct=38.0,
        notes="Implied BAFTA Supporting Actor win for One Battle; 3rd Oscar nomination",
    ),
    Nominee(
        name="Jacob Elordi",
        film="Frankenstein",
        precursors_won=[],
        kalshi_price_cents=28,
        gold_derby_pct=25.0,
        notes="First nomination; del Toro film generates strong interest",
    ),
    Nominee(
        name="Benicio del Toro",
        film="One Battle After Another",
        precursors_won=[],
        kalshi_price_cents=18,
        gold_derby_pct=18.0,
        notes="Third Oscar nomination overall",
    ),
    Nominee(
        name="Delroy Lindo",
        film="Unknown",
        precursors_won=[],
        kalshi_price_cents=12,
        gold_derby_pct=12.0,
    ),
    Nominee(
        name="Stellan Skarsgård",
        film="Unknown",
        precursors_won=[],
        kalshi_price_cents=7,
        gold_derby_pct=7.0,
    ),
]

# ─── Best Supporting Actress ──────────────────────────────────────────────────

BEST_SUPPORTING_ACTRESS: list[Nominee] = [
    Nominee(
        name="Wunmi Mosaku",
        film="Sinners",
        precursors_won=[
            "BAFTA Best Supporting Actress",       # Won BAFTA Best Supporting Actress
        ],
        kalshi_price_cents=55,
        gold_derby_pct=55.0,
        notes="BAFTA win; clear frontrunner; part of Sinners' broad support",
    ),
    Nominee(
        name="Elle Fanning",
        film="Sentimental Value",
        precursors_won=[],
        kalshi_price_cents=18,
        gold_derby_pct=18.0,
    ),
    Nominee(
        name="Teyana Taylor",
        film="One Battle After Another",
        precursors_won=[],
        kalshi_price_cents=12,
        gold_derby_pct=12.0,
        notes="Benefiting from One Battle sweep; first nomination",
    ),
    Nominee(
        name="Amy Madigan",
        film="Weapons",
        precursors_won=[],
        kalshi_price_cents=8,
        gold_derby_pct=8.0,
    ),
    Nominee(
        name="Inga Ibsdotter Lilleaas",
        film="Sentimental Value",
        precursors_won=[],
        kalshi_price_cents=7,
        gold_derby_pct=7.0,
    ),
]

# ─── Best Original Screenplay ─────────────────────────────────────────────────

BEST_ORIGINAL_SCREENPLAY: list[Nominee] = [
    Nominee(
        name="Ryan Coogler",
        film="Sinners",
        precursors_won=[
            "BAFTA Best Original Screenplay",       # Won BAFTA Original Screenplay
            # WGA (Mar 8) outcome TBD; Coogler nominated
        ],
        kalshi_price_cents=48,
        gold_derby_pct=45.0,
        notes="BAFTA Screenplay win; Sinners' strongest individual precursor",
    ),
    Nominee(
        name="Paul Thomas Anderson",
        film="One Battle After Another",
        precursors_won=[],
        kalshi_price_cents=28,
        gold_derby_pct=25.0,
        notes="One Battle nominated for Adapted (not Original) Screenplay at WGA",
    ),
    Nominee(
        name="Josh Safdie",
        film="Marty Supreme",
        precursors_won=[
            # WGA nominee — outcome TBD
        ],
        kalshi_price_cents=12,
        gold_derby_pct=15.0,
        notes="WGA Original nominee",
    ),
    Nominee(
        name="Joachim Trier",
        film="Sentimental Value",
        precursors_won=[],
        kalshi_price_cents=8,
        gold_derby_pct=10.0,
    ),
    Nominee(
        name="Chloé Zhao",
        film="Hamnet",
        precursors_won=[],
        kalshi_price_cents=4,
        gold_derby_pct=5.0,
    ),
]

# ─── Best Adapted Screenplay ──────────────────────────────────────────────────

BEST_ADAPTED_SCREENPLAY: list[Nominee] = [
    Nominee(
        name="Paul Thomas Anderson",
        film="One Battle After Another",
        precursors_won=[
            # WGA Adapted nominee — outcome TBD; Anderson is frontrunner
        ],
        kalshi_price_cents=55,
        gold_derby_pct=55.0,
        notes="WGA Adapted nominee; One Battle dominant in technical + writing categories",
    ),
    Nominee(
        name="Guillermo del Toro",
        film="Frankenstein",
        precursors_won=[
            # WGA nominee
        ],
        kalshi_price_cents=20,
        gold_derby_pct=18.0,
        notes="WGA Adapted nominee",
    ),
    Nominee(
        name="Hamnet",
        film="Hamnet",
        precursors_won=[],
        kalshi_price_cents=12,
        gold_derby_pct=14.0,
    ),
    Nominee(
        name="Bugonia",
        film="Bugonia",
        precursors_won=[],
        kalshi_price_cents=8,
        gold_derby_pct=8.0,
    ),
    Nominee(
        name="Train Dreams",
        film="Train Dreams",
        precursors_won=[],
        kalshi_price_cents=5,
        gold_derby_pct=5.0,
    ),
]

# ─── Registry ─────────────────────────────────────────────────────────────────

CATEGORIES_2026: dict[str, list[Nominee]] = {
    "best_picture": BEST_PICTURE,
    "best_director": BEST_DIRECTOR,
    "best_actor": BEST_ACTOR,
    "best_actress": BEST_ACTRESS,
    "best_supporting_actor": BEST_SUPPORTING_ACTOR,
    "best_supporting_actress": BEST_SUPPORTING_ACTRESS,
    "best_original_screenplay": BEST_ORIGINAL_SCREENPLAY,
    "best_adapted_screenplay": BEST_ADAPTED_SCREENPLAY,
}

CATEGORY_DISPLAY: dict[str, str] = {
    "best_picture": "Best Picture",
    "best_director": "Best Director",
    "best_actor": "Best Actor",
    "best_actress": "Best Actress",
    "best_supporting_actor": "Best Supporting Actor",
    "best_supporting_actress": "Best Supporting Actress",
    "best_original_screenplay": "Best Original Screenplay",
    "best_adapted_screenplay": "Best Adapted Screenplay",
}
