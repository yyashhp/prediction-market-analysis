"""98th Academy Awards (2026) Prediction Analysis.

Runs the precursor-based probability model for all major Oscar categories,
compares model output to Kalshi market prices and Gold Derby consensus,
identifies edge opportunities, and explains the Kelly-size recommendation.

Usage:
    uv run python -m src.analysis.oscar.oscar_analysis
    uv run python -m src.analysis.oscar.oscar_analysis --bankroll 5000
    uv run python -m src.analysis.oscar.oscar_analysis --json > output/oscar_2026.json
"""

from __future__ import annotations

import argparse
import json

from src.analysis.oscar.model import CategoryPrediction, kelly_bet_size, run_all_categories

# ─── Formatting helpers ───────────────────────────────────────────────────────

_BAR_WIDTH = 30


def _prob_bar(prob: float, width: int = _BAR_WIDTH) -> str:
    filled = round(prob * width)
    return "█" * filled + "░" * (width - filled)


def _edge_indicator(edge: float | None) -> str:
    if edge is None:
        return "  —  "
    if edge > 0.05:
        return f"🟢 +{edge*100:.1f}pp"
    if edge > 0.02:
        return f"🟡 +{edge*100:.1f}pp"
    if edge < -0.05:
        return f"🔴 {edge*100:.1f}pp"
    if edge < -0.02:
        return f"🟠 {edge*100:.1f}pp"
    return f"⚪ {edge*100:+.1f}pp"


def _format_category(cat: CategoryPrediction, bankroll: float) -> str:
    lines = [
        "",
        f"{'═'*72}",
        f"  {cat.category_display.upper()}",
        f"{'═'*72}",
    ]

    if cat.pending_precursors:
        lines.append("  ⏳ Pending precursors (results not yet known):")
        for p in cat.pending_precursors:
            lines.append(f"     • {p}")
        lines.append("")

    header = (
        f"  {'Nominee':<30} {'Model':>6}  {'Market':>7}  {'Gold Derby':>10}  "
        f"{'Edge vs Mkt':>12}  {'Kelly $':>8}"
    )
    lines.append(header)
    lines.append(f"  {'─'*30} {'─'*6}  {'─'*7}  {'─'*10}  {'─'*12}  {'─'*8}")

    for r in cat.nominees:
        model_str = f"{r.model_prob*100:5.1f}%"
        mkt_str = f"{r.kalshi_price*100:.0f}¢" if r.kalshi_price is not None else "  —"
        gd_str = f"{r.gold_derby_prob*100:.1f}%" if r.gold_derby_prob is not None else "  —"
        edge_str = _edge_indicator(r.edge_vs_market)
        kelly_size = kelly_bet_size(r, bankroll)
        kelly_str = f"${kelly_size:,.0f}" if kelly_size else "—"

        lines.append(
            f"  {r.nominee:<30} {model_str:>6}  {mkt_str:>7}  {gd_str:>10}  "
            f"{edge_str:>16}  {kelly_str:>8}"
        )

    # Probability bar chart
    lines.append("")
    lines.append("  Probability distribution:")
    for r in cat.nominees:
        bar = _prob_bar(r.model_prob)
        lines.append(f"  {r.nominee:<25} {bar} {r.model_prob*100:5.1f}%")

    # Precursor summary
    lines.append("")
    lines.append("  Precursors won:")
    any_won = False
    for r in cat.nominees:
        if r.precursors_won:
            any_won = True
            for p in r.precursors_won:
                lines.append(f"    ✓ {r.nominee}: {p}")
    if not any_won:
        lines.append("    (none yet — all pending)")

    # Top recommendation
    top = cat.top_pick
    best_edge = cat.best_edge_opportunity
    lines.append("")
    lines.append(f"  📊 Model top pick: {top.nominee} ({top.model_prob*100:.1f}%)")

    if best_edge and best_edge.edge_vs_market is not None and best_edge.edge_vs_market > 0.02:
        action = "BUY YES"
        kelly_size = kelly_bet_size(best_edge, bankroll)
        lines.append(
            f"  💰 Best edge: {action} {best_edge.nominee} at "
            f"{(best_edge.kalshi_price or 0)*100:.0f}¢ "
            f"(model: {best_edge.model_prob*100:.1f}%, "
            f"edge: +{best_edge.edge_vs_market*100:.1f}pp, "
            f"Kelly: ${kelly_size:,.0f})"
        )
    elif best_edge and best_edge.edge_vs_market is not None and best_edge.edge_vs_market < -0.05:
        # Large negative edge = market overpricing this nominee vs model → buy NO on this
        lines.append(
            f"  💰 Consider BUY NO on {best_edge.nominee}: "
            f"market {(best_edge.kalshi_price or 0)*100:.0f}¢ vs model {best_edge.model_prob*100:.1f}%"
        )
    else:
        lines.append("  ⚪ No edge above threshold vs current Kalshi prices")

    return "\n".join(lines)


def format_market_making_note() -> str:
    """Explanation of when to market-make vs selectively take."""
    return """
┌─────────────────────────────────────────────────────────────────────────┐
│  KALSHI MARKET MAKING INCENTIVES — CONTEXT FOR OSCAR MARKETS            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Who posts bid/ask on thin Kalshi entertainment markets?                │
│  ───────────────────────────────────────────────────────               │
│  • Retail participants copying Gold Derby odds + adding a spread        │
│  • True believers posting their personal probability guess              │
│  • Speculators trying to "be the house" (collect the spread)            │
│  • NOT professional quant desks (too thin, too niche)                   │
│                                                                         │
│  Kalshi fee structure (as of 2026):                                     │
│  ───────────────────────────────────────────────────────               │
│  • Takers (market orders): ~7% of potential profit per contract         │
│  • Makers (limit orders): same fee schedule; NO rebate unlike equities  │
│  • Minimum fee: 1¢ per contract                                         │
│  • Official MM program: fee rebates + direct compensation for qualified │
│    institutional MMs posting continuous two-sided quotes                │
│                                                                         │
│  When to TAKE vs MAKE:                                                  │
│  ───────────────────────────────────────────────────────               │
│  TAKE if: |model_prob - market_price| > spread + fee (~3-5pp total)    │
│  MAKE if: model shows fair value within spread but market is wide        │
│           and you're confident in your calibration                       │
│                                                                         │
│  ⚠️  Warning: Making in Oscar markets means sitting with inventory      │
│  through vote-close (Mar 5) to ceremony (Mar 15).  If new info          │
│  arrives (SAG results Mar 1, WGA Mar 8), you must update or cover.      │
│  Inventory risk is higher than it looks for a 10-day event.             │
│                                                                         │
│  ✅ Selective taking is lower risk: enter once, hold to ceremony,       │
│  collect $1 if correct.  No inventory, no delta management needed.      │
└─────────────────────────────────────────────────────────────────────────┘
"""


def format_pending_precursors_note() -> str:
    return """
⏳ UPCOMING PRECURSORS (will update model probabilities):
   Feb 28 — PGA Awards (Darryl F. Zanuck Award = Best Picture) [TOMORROW]
   Mar  1 — SAG Awards (Lead Actor, Lead Actress, Ensemble, Supporting)
   Mar  8 — WGA Awards (Original, Adapted Screenplay)
   Mar  8 — ASC Awards (Cinematography)
   Mar 15 — 98th Academy Awards ceremony

Strategy: Check model after each precursor. SAG on Mar 1 is especially
important — it's the strongest predictor for Lead Actor, Lead Actress,
and Supporting Actress categories. PGA (Feb 28) will either confirm or
complicate the One Battle frontrunner status for Best Picture.
"""


# ─── Main analysis function ───────────────────────────────────────────────────


def run_analysis(bankroll: float = 10_000.0, as_json: bool = False) -> None:
    """Run all category predictions and print the analysis."""
    predictions = run_all_categories()

    if as_json:
        output = {}
        for slug, cat in predictions.items():
            output[slug] = {
                "category": cat.category_display,
                "pending_precursors": cat.pending_precursors,
                "nominees": [
                    {
                        "name": r.nominee,
                        "film": r.film,
                        "model_prob": r.model_prob,
                        "kalshi_price": r.kalshi_price,
                        "gold_derby_prob": r.gold_derby_prob,
                        "edge_vs_market": r.edge_vs_market,
                        "edge_vs_consensus": r.edge_vs_consensus,
                        "kelly_fraction": r.kelly_fraction,
                        "kelly_dollars": kelly_bet_size(r, bankroll),
                        "precursors_won": r.precursors_won,
                        "raw_score": r.raw_score,
                        "notes": r.notes,
                    }
                    for r in cat.nominees
                ],
            }
        print(json.dumps(output, indent=2))
        return

    print("=" * 72)
    print("  98TH ACADEMY AWARDS — PREDICTION MODEL vs KALSHI MARKET")
    print(f"  Generated: 2026-02-26  |  Ceremony: ~2026-03-15  |  Bankroll: ${bankroll:,.0f}")
    print("=" * 72)

    # Model confidence note
    print("""
Model architecture: Precursor-correlation scoring + per-category softmax
Scores = ε(0.10 base) + sum of historical correlations for precursors won.
Per-category temperatures (τ=0.50–0.80) calibrated to match historical win rates.
NOT fitted to 2026 data → no look-ahead bias.  This is a prior; update
after each remaining precursor (PGA Feb 28, SAG Mar 1, WGA Mar 8).
""")

    print(format_pending_precursors_note())
    print(format_market_making_note())

    # Print each category
    for _slug, cat in predictions.items():
        print(_format_category(cat, bankroll))

    # Executive summary
    print("\n" + "=" * 72)
    print("  EXECUTIVE SUMMARY — TOP EDGE OPPORTUNITIES")
    print("=" * 72)

    edge_opps = []
    for _slug, cat in predictions.items():
        for r in cat.nominees:
            if r.edge_vs_market is not None and abs(r.edge_vs_market) > 0.03:
                edge_opps.append((cat.category_display, r))

    edge_opps.sort(key=lambda x: abs(x[1].edge_vs_market or 0), reverse=True)

    if edge_opps:
        print(f"\n  {'Category':<28} {'Nominee':<28} {'Model':>6} {'Market':>7} {'Edge':>10} {'Action':>12}")
        print(f"  {'─'*28} {'─'*28} {'─'*6} {'─'*7} {'─'*10} {'─'*12}")
        for cat_name, r in edge_opps[:10]:
            edge = r.edge_vs_market or 0
            action = (
                f"BUY YES ({(r.kalshi_price or 0)*100:.0f}¢)"
                if edge > 0
                else f"BUY NO ({100-(r.kalshi_price or 0)*100:.0f}¢)"
            )
            print(
                f"  {cat_name:<28} {r.nominee:<28} "
                f"{r.model_prob*100:5.1f}%  "
                f"{(r.kalshi_price or 0)*100:5.0f}¢  "
                f"{edge*100:+6.1f}pp  {action:>12}"
            )
    else:
        print("\n  No edges above 3pp threshold found under current data.")

    print(
        "\n  NOTE: Model is PRIOR only — add PGA/SAG/WGA results when available."
        "\n  The SAG Awards on Mar 1 will substantially update Best Actor, Actress,"
        "\n  and Supporting Actress categories. PGA (Feb 28) updates Best Picture."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="98th Oscar prediction analysis")
    parser.add_argument("--bankroll", type=float, default=10_000.0, help="Bankroll in $ for Kelly sizing")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    args = parser.parse_args()
    run_analysis(bankroll=args.bankroll, as_json=args.json)
