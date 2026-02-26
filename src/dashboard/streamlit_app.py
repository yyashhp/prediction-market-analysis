"""Streamlit prediction market RV research dashboard.

Organizes all fetched contracts by topic and event group, rendering
term structure curves and threshold CDF plots for each detected series.
This is a research surface — not an alert system. Show the structure,
let the analyst spot the patterns.

Run:
    uv run streamlit run src/dashboard/streamlit_app.py
    make dashboard
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # must be before pyplot import

from datetime import datetime  # noqa: E402

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.dashboard.app import create_feed_manager  # noqa: E402
from src.dashboard.config import DashboardConfig  # noqa: E402
from src.live.feed_manager import MarketSnapshot  # noqa: E402
from src.rv.classifier import Topic  # noqa: E402
from src.rv.info_efficiency import EdgeOpportunity, classify_info_efficiency  # noqa: E402
from src.rv.matcher import ContractSeries, _extract_threshold, detect_series  # noqa: E402
from src.rv.normalizer import NormalizedQuote  # noqa: E402

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PM RV Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Prediction Market Relative Value Research Dashboard"},
)

# ─── Data layer ───────────────────────────────────────────────────────────────


@st.cache_resource(show_spinner=False)
def _get_feed_manager():
    """Singleton FeedManager — HTTP clients created once for the app lifetime."""
    return create_feed_manager(DashboardConfig.from_env())


def _do_fetch() -> MarketSnapshot:
    with st.spinner("Fetching markets from Kalshi and Polymarket…"):
        return _get_feed_manager().snapshot()


# Initialise session state on first load
if "snapshot" not in st.session_state:
    st.session_state["snapshot"] = _do_fetch()
    st.session_state["fetched_at"] = datetime.now()


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _quotes_to_df(quotes: list[NormalizedQuote]) -> pd.DataFrame:
    rows = []
    for q in quotes:
        rows.append(
            {
                "Title": q.title,
                "Venue": q.venue.capitalize(),
                "Topic": q.topic.capitalize() if q.topic else "—",
                "Mid": round(q.prob_mid_or_last, 4),
                "Bid": round(q.prob_bid, 4) if q.prob_bid is not None else None,
                "Ask": round(q.prob_ask, 4) if q.prob_ask is not None else None,
                "Spread pp": round(q.spread * 100, 2) if q.spread is not None else None,
                "Vol 24h": round(q.volume_24h or 0),
                "OI": q.open_interest or 0,
                "Total Vol": round(q.total_volume or 0),
                "Closes": q.close_time.date() if q.close_time else None,
            }
        )
    return pd.DataFrame(rows)


def _polymarket_quotes_to_df(quotes: list[NormalizedQuote]) -> pd.DataFrame:
    """Flat table for Polymarket binary Yes/No questions."""
    rows = []
    for q in quotes:
        rating = classify_info_efficiency(q)
        rows.append(
            {
                "Question": q.title,
                "Topic": q.topic.capitalize() if q.topic else "—",
                "Ref Market": rating.backing_source.value,
                "Edge": _EDGE_LABELS[rating.edge_opportunity],
                "Mid": round(q.prob_mid_or_last, 4),
                "Bid": round(q.prob_bid, 4) if q.prob_bid is not None else None,
                "Ask": round(q.prob_ask, 4) if q.prob_ask is not None else None,
                "Spread pp": round(q.spread * 100, 2) if q.spread is not None else None,
                "Vol 24h": round(q.volume_24h or 0),
                "Liquidity": q.open_interest or 0,
                "Total Vol": round(q.total_volume or 0),
                "Closes": q.close_time.date() if q.close_time else None,
            }
        )
    return pd.DataFrame(rows)


def _kalshi_events_summary_df(kalshi_quotes: list[NormalizedQuote]) -> pd.DataFrame:
    """One row per Kalshi event group: Event, Topic, # Outcomes, Best Spread, Total Vol, Closes."""
    groups: dict[str, list[NormalizedQuote]] = {}
    for q in kalshi_quotes:
        key = q.event_group or q.market_id
        groups.setdefault(key, []).append(q)

    rows = []
    for event_key, gq in groups.items():
        topic = gq[0].topic.capitalize() if gq[0].topic else "—"
        spreads = [q.spread for q in gq if q.spread is not None]
        best_spread = round(min(spreads) * 100, 2) if spreads else None
        total_vol = sum(q.total_volume or 0 for q in gq)
        close_times = [q.close_time for q in gq if q.close_time]
        closes = min(close_times).date() if close_times else None
        rating = classify_info_efficiency(gq[0])
        rows.append(
            {
                "Event": event_key,
                "Topic": topic,
                "Ref Market": rating.backing_source.value,
                "Edge": _EDGE_LABELS[rating.edge_opportunity],
                "Outcomes": len(gq),
                "Best Spread pp": best_spread,
                "Total Vol ($)": round(total_vol),
                "Closes": closes,
            }
        )
    return pd.DataFrame(rows).sort_values("Total Vol ($)", ascending=False).reset_index(drop=True)


def _kalshi_outcomes_df(quotes: list[NormalizedQuote]) -> pd.DataFrame:
    """Per-outcome detail table for a single Kalshi event (prices shown in cents 1–99)."""
    rows = []
    for q in sorted(quotes, key=lambda q: q.prob_mid_or_last, reverse=True):
        rows.append(
            {
                "Outcome": q.title,
                "Yes Mid %": round(q.prob_mid_or_last * 100, 1),
                "Yes Bid ¢": round(q.prob_bid * 100) if q.prob_bid is not None else None,
                "Yes Ask ¢": round(q.prob_ask * 100) if q.prob_ask is not None else None,
                "Spread pp": round(q.spread * 100, 2) if q.spread is not None else None,
                "Vol 24h ($)": round(q.volume_24h or 0),
                "OI": q.open_interest or 0,
                "Closes": q.close_time.date() if q.close_time else None,
            }
        )
    return pd.DataFrame(rows)


_EDGE_LABELS: dict[EdgeOpportunity, str] = {
    EdgeOpportunity.VERY_LOW: "🔴 Efficient",
    EdgeOpportunity.LOW: "🟠 Low Edge",
    EdgeOpportunity.MEDIUM: "🟡 Model Edge",
    EdgeOpportunity.HIGH: "🟢 Potential Edge",
}

# Sort key so tables order HIGH → MEDIUM → LOW → VERY_LOW
_EDGE_SORT: dict[EdgeOpportunity, int] = {
    EdgeOpportunity.HIGH: 0,
    EdgeOpportunity.MEDIUM: 1,
    EdgeOpportunity.LOW: 2,
    EdgeOpportunity.VERY_LOW: 3,
}


def _edge_opportunities_df(quotes: list[NormalizedQuote]) -> pd.DataFrame:
    """Table used in the Edge Opportunities tab — one row per contract."""
    rows = []
    for q in quotes:
        rating = classify_info_efficiency(q)
        rows.append(
            {
                "Title": q.title,
                "Venue": q.venue.capitalize(),
                "Topic": q.topic.capitalize() if q.topic else "—",
                "Reference Market": rating.backing_source.value,
                "Edge": _EDGE_LABELS[rating.edge_opportunity],
                "_edge_sort": _EDGE_SORT[rating.edge_opportunity],
                "Spread pp": round(q.spread * 100, 2) if q.spread is not None else None,
                "Total Vol": round(q.total_volume or 0),
                "Closes": q.close_time.date() if q.close_time else None,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return (
        df.sort_values(["_edge_sort", "Total Vol"], ascending=[True, False])
        .drop(columns=["_edge_sort"])
        .reset_index(drop=True)
    )


def _topic_efficiency_summary_df(quotes: list[NormalizedQuote]) -> pd.DataFrame:
    """One row per topic: counts, avg spread, dominant backing source, edge level."""
    from collections import Counter, defaultdict

    topic_groups: dict[str, list[NormalizedQuote]] = defaultdict(list)
    for q in quotes:
        topic_groups[q.topic or "other"].append(q)

    rows = []
    for topic, tq in topic_groups.items():
        ratings = [classify_info_efficiency(q) for q in tq]
        spreads = [q.spread * 100 for q in tq if q.spread is not None]
        avg_spread = round(sum(spreads) / len(spreads), 1) if spreads else None
        dominant_edge = Counter(r.edge_opportunity for r in ratings).most_common(1)[0][0]
        dominant_source = Counter(r.backing_source for r in ratings).most_common(1)[0][0]
        rows.append(
            {
                "Topic": topic.capitalize(),
                "Markets": len(tq),
                "Avg Spread (pp)": avg_spread,
                "Reference Market": dominant_source.value,
                "Edge Level": _EDGE_LABELS[dominant_edge],
                "_edge_sort": _EDGE_SORT[dominant_edge],
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return (
        df.sort_values(["_edge_sort", "Markets"], ascending=[True, False])
        .drop(columns=["_edge_sort"])
        .reset_index(drop=True)
    )


def _term_structure_chart(
    series_by_venue: dict[str, list[NormalizedQuote]],
    title: str,
) -> plt.Figure:
    """Plot probability vs resolution date, one line per venue."""
    fig, ax = plt.subplots(figsize=(11, 4))
    palette = {"kalshi": "#e06c75", "polymarket": "#61afef"}

    for venue, quotes in series_by_venue.items():
        quotes_dated = sorted([q for q in quotes if q.close_time], key=lambda q: q.close_time)
        if not quotes_dated:
            continue
        xs = [q.close_time for q in quotes_dated]
        ys = [q.prob_mid_or_last * 100 for q in quotes_dated]
        color = palette.get(venue, "#abb2bf")
        ax.plot(xs, ys, "o-", color=color, label=venue.capitalize(), lw=2, ms=7, zorder=3)

        # Bid/ask shading
        lo = [q.prob_bid * 100 if q.prob_bid is not None else q.prob_mid_or_last * 100 for q in quotes_dated]
        hi = [q.prob_ask * 100 if q.prob_ask is not None else q.prob_mid_or_last * 100 for q in quotes_dated]
        ax.fill_between(xs, lo, hi, color=color, alpha=0.12)

        # Annotate each point
        for x, y in zip(xs, ys):
            ax.annotate(
                f"{y:.1f}%",
                (x, y),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8,
                color=color,
            )

    ax.set_ylabel("Implied Probability (%)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate(rotation=30)
    ax.grid(True, alpha=0.2, linestyle="--")
    ax.legend(loc="upper left")
    ax.set_title(title, fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


def _cdf_chart(
    pts: list[tuple[NormalizedQuote, float]],
    title: str,
    fit_normal: bool = True,
) -> plt.Figure:
    """Plot P(X > threshold) vs threshold, optionally overlay fitted normal."""
    pts = sorted(pts, key=lambda x: x[1])
    xs = np.array([t for _, t in pts])
    ys = np.array([q.prob_mid_or_last * 100 for q, _ in pts])

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(xs, ys, "o-", color="#98c379", lw=2, ms=8, label="Market mid", zorder=3)

    lo = [q.prob_bid * 100 if q.prob_bid is not None else q.prob_mid_or_last * 100 for q, _ in pts]
    hi = [q.prob_ask * 100 if q.prob_ask is not None else q.prob_mid_or_last * 100 for q, _ in pts]
    ax.fill_between(xs, lo, hi, color="#98c379", alpha=0.15, label="Bid/Ask band")

    residuals: dict[float, float] = {}

    if fit_normal and len(pts) >= 3:
        try:
            from scipy.optimize import curve_fit
            from scipy.stats import norm

            cdf_vals = 1.0 - ys / 100.0
            std_guess = max(float(np.std(xs)), 1e-3)
            popt, _ = curve_fit(
                lambda x, mu, sigma: norm.cdf(x, mu, sigma),
                xs,
                cdf_vals,
                p0=[float(np.mean(xs)), std_guess],
                maxfev=5000,
            )
            mu, sigma = float(popt[0]), float(popt[1])
            if sigma > 0:
                xr = np.linspace(xs[0] - 2 * abs(sigma), xs[-1] + 2 * abs(sigma), 300)
                ax.plot(
                    xr,
                    (1 - norm.cdf(xr, mu, sigma)) * 100,
                    "--",
                    color="#e5c07b",
                    lw=1.5,
                    label=f"Fitted Normal  μ={mu:.2f}  σ={sigma:.2f}",
                )
                # Residuals
                for x, y in zip(xs, ys):
                    r = y - (1 - norm.cdf(x, mu, sigma)) * 100
                    residuals[x] = r
                    color = "#e06c75" if abs(r) > 2 else "#abb2bf"
                    ax.annotate(
                        f"{r:+.1f}pp",
                        (x, y),
                        textcoords="offset points",
                        xytext=(0, 13),
                        ha="center",
                        fontsize=8,
                        color=color,
                    )
        except Exception:
            pass

    if not residuals:
        # No fit — just annotate mid values
        for x, y in zip(xs, ys):
            ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=8)

    ax.set_xlabel("Threshold")
    ax.set_ylabel("P(X > threshold) (%)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(True, alpha=0.2, linestyle="--")
    ax.legend(loc="upper right")
    ax.set_title(title, fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙ Controls")

    if st.button("↺ Refresh Data", type="primary", use_container_width=True):
        st.session_state["snapshot"] = _do_fetch()
        st.session_state["fetched_at"] = datetime.now()
        st.rerun()

    st.markdown("---")

    _all_topics = ["weather", "sports", "macro", "crypto", "politics", "entertainment", "other"]
    selected_topics = st.multiselect(
        "Topics",
        options=_all_topics,
        default=_all_topics,  # show everything by default — filter down as needed
        format_func=str.capitalize,
    )

    selected_venues = st.multiselect(
        "Venues",
        options=["kalshi", "polymarket"],
        default=["kalshi", "polymarket"],
        format_func=str.capitalize,
    )

    st.markdown("---")
    st.markdown("**Liquidity filters**")
    min_total_vol = st.number_input("Min total volume ($)", min_value=0, value=0, step=500)
    min_oi = st.number_input("Min open interest", min_value=0, value=0, step=50)
    min_series_size = st.slider("Min contracts per series", min_value=2, max_value=5, value=2)

    st.markdown("---")
    st.caption("Refresh pulls fresh data from the APIs.\n\nFilters apply to all views without re-fetching.")

# ─── Apply filters ────────────────────────────────────────────────────────────

snapshot: MarketSnapshot = st.session_state["snapshot"]
fetched_at: datetime = st.session_state.get("fetched_at", datetime.now())


def _filter(quotes: list[NormalizedQuote]) -> list[NormalizedQuote]:
    return [
        q
        for q in quotes
        if q.topic in selected_topics
        and q.venue in selected_venues
        and (q.total_volume or 0) >= min_total_vol
        and (q.open_interest or 0) >= min_oi
    ]


kalshi_shown = _filter(snapshot.kalshi_quotes)
poly_shown = _filter(snapshot.polymarket_quotes)
all_shown = kalshi_shown + poly_shown

# Pre-detect all series (used by Term Structures + Threshold CDFs tabs)
all_series: list[ContractSeries] = []
for _tv in selected_topics:
    try:
        _topic_enum = Topic(_tv)
    except ValueError:
        continue
    _tq = [q for q in all_shown if q.topic == _tv]
    all_series.extend(detect_series(_tq, _topic_enum, min_series_size=min_series_size))

term_series = [s for s in all_series if s.series_type == "term_structure"]
cdf_series = [s for s in all_series if s.series_type == "threshold"]

# ─── Page header ──────────────────────────────────────────────────────────────

st.markdown("# 📊 Prediction Market RV Dashboard")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Kalshi", f"{len(snapshot.kalshi_quotes):,}", f"{len(kalshi_shown)} shown")
c2.metric("Polymarket", f"{len(snapshot.polymarket_quotes):,}", f"{len(poly_shown)} shown")
c3.metric("Term Structures", len(term_series))
c4.metric("Threshold CDFs", len(cdf_series))
c5.metric("As of", fetched_at.strftime("%H:%M:%S"), f"fetch {snapshot.fetch_duration_seconds:.1f}s")

st.markdown("---")

# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab_poly, tab_kalshi, tab_edge, tab_groups, tab_term, tab_cdf, tab_oscar = st.tabs(
    [
        "📊  Polymarket",
        "🎯  Kalshi Events",
        "🔍  Edge Opportunities",
        "🔗  Event Groups",
        "📈  Term Structures",
        "📉  Threshold CDFs",
        "🏆  Oscar 2026",
    ]
)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — Polymarket
# Flat table of binary Yes/No questions from Polymarket.
# Each row is one question with a single bid/ask/mid.
# ════════════════════════════════════════════════════════════════════════════════

with tab_poly:
    st.markdown(f"**{len(poly_shown):,} binary markets** from Polymarket")

    if not poly_shown:
        st.info("No Polymarket contracts match the current filters.")
    else:
        df_poly = _polymarket_quotes_to_df(poly_shown)
        st.dataframe(
            df_poly,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Question": st.column_config.TextColumn("Question", width="large"),
                "Ref Market": st.column_config.TextColumn(
                    "Ref Market",
                    help="External market/model that informs this price. 'None' = no professional reference → higher edge potential.",
                ),
                "Edge": st.column_config.TextColumn(
                    "Edge",
                    help="🟢 Potential Edge: no reference market. 🟡 Model Edge: reference exists but retail don't use it. 🟠 Low: sports books. 🔴 Efficient: CME/crypto.",
                ),
                "Mid": st.column_config.ProgressColumn(
                    "Mid (Yes %)",
                    help="Implied probability of Yes outcome (0–1). Bar fill = probability.",
                    min_value=0.0,
                    max_value=1.0,
                    format="%.3f",
                ),
                "Bid": st.column_config.NumberColumn("Bid (Yes)", format="%.3f"),
                "Ask": st.column_config.NumberColumn("Ask (Yes)", format="%.3f"),
                "Spread pp": st.column_config.NumberColumn("Spread (pp)", format="%.2f"),
                "Vol 24h": st.column_config.NumberColumn("Vol 24h ($)", format="$%,.0f"),
                "Liquidity": st.column_config.NumberColumn(
                    "Liquidity ($)",
                    help="Liquidity depth in USDC — proxy for open interest (true OI not in gamma API).",
                    format="$%,.0f",
                ),
                "Total Vol": st.column_config.NumberColumn("Total Vol ($)", format="$%,.0f"),
                "Closes": st.column_config.DateColumn("Closes"),
            },
        )

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — Kalshi Events
# Kalshi markets grouped by event (event_ticker). Each event can have multiple
# outcome sub-markets (e.g. "Fed cuts ≥25bp", "≥50bp", "≥75bp"). Shows an
# event summary table, then a selectbox to drill into individual outcomes.
# ════════════════════════════════════════════════════════════════════════════════

with tab_kalshi:
    # Build event groups
    _kalshi_groups: dict[str, list[NormalizedQuote]] = {}
    for _q in kalshi_shown:
        _key = _q.event_group or _q.market_id
        _kalshi_groups.setdefault(_key, []).append(_q)

    n_events = len(_kalshi_groups)
    st.markdown(f"**{len(kalshi_shown):,} markets** across **{n_events:,} events** from Kalshi")

    if not kalshi_shown:
        st.info("No Kalshi contracts match the current filters.")
    else:
        # ── Event summary table ───────────────────────────────────────────────
        st.markdown("##### All Events")
        summary_df = _kalshi_events_summary_df(kalshi_shown)
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Event": st.column_config.TextColumn("Event Ticker", width="medium"),
                "Topic": st.column_config.TextColumn("Topic"),
                "Ref Market": st.column_config.TextColumn(
                    "Ref Market",
                    help="External market/model that informs this price.",
                ),
                "Edge": st.column_config.TextColumn(
                    "Edge",
                    help="🟢 Potential Edge: no reference market. 🟡 Model Edge: reference exists but retail don't use it. 🟠 Low: sports books. 🔴 Efficient: CME/crypto.",
                ),
                "Outcomes": st.column_config.NumberColumn("# Outcomes", format="%d"),
                "Best Spread pp": st.column_config.NumberColumn("Best Spread (pp)", format="%.2f"),
                "Total Vol ($)": st.column_config.NumberColumn("Total Vol ($)", format="$%,.0f"),
                "Closes": st.column_config.DateColumn("Closes"),
            },
        )

        # ── Outcome drill-down ────────────────────────────────────────────────
        st.markdown("##### Outcome Detail")
        sorted_event_keys = list(summary_df["Event"])
        sel_event = st.selectbox(
            f"Select event ({n_events} events — sorted by total volume)",
            options=sorted_event_keys,
            format_func=lambda k: (
                f"{k}  [{len(_kalshi_groups.get(k, []))} outcomes]  "
                f"${sum(q.total_volume or 0 for q in _kalshi_groups.get(k, [])):,.0f} total vol"
            ),
        )

        if sel_event:
            event_quotes = _kalshi_groups.get(sel_event, [])
            topic_label = event_quotes[0].topic.capitalize() if event_quotes and event_quotes[0].topic else "—"
            st.markdown(f"**{sel_event}** &nbsp;·&nbsp; {topic_label} &nbsp;·&nbsp; {len(event_quotes)} outcomes")
            outcomes_df = _kalshi_outcomes_df(event_quotes)
            st.dataframe(
                outcomes_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Outcome": st.column_config.TextColumn("Outcome", width="large"),
                    "Yes Mid %": st.column_config.ProgressColumn(
                        "Yes Mid %",
                        help="Implied probability of Yes outcome. Bar fill = probability.",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                    ),
                    "Yes Bid ¢": st.column_config.NumberColumn("Yes Bid ¢", format="%d¢"),
                    "Yes Ask ¢": st.column_config.NumberColumn("Yes Ask ¢", format="%d¢"),
                    "Spread pp": st.column_config.NumberColumn("Spread (pp)", format="%.2f"),
                    "Vol 24h ($)": st.column_config.NumberColumn("Vol 24h ($)", format="$%,.0f"),
                    "OI": st.column_config.NumberColumn("OI (contracts)", format="%,d"),
                    "Closes": st.column_config.DateColumn("Closes"),
                },
            )

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — Edge Opportunities
# Classifies every contract by information efficiency.  Markets with no external
# reference price (entertainment, niche events) are flagged as high-edge.
# Markets backed by CME/sports-books/crypto are flagged as efficient.
# ════════════════════════════════════════════════════════════════════════════════

with tab_edge:
    # Count markets by edge tier across both venues
    _all_ratings = [(q, classify_info_efficiency(q)) for q in all_shown]
    _high = [(q, r) for q, r in _all_ratings if r.edge_opportunity == EdgeOpportunity.HIGH]
    _medium = [(q, r) for q, r in _all_ratings if r.edge_opportunity == EdgeOpportunity.MEDIUM]
    _low = [(q, r) for q, r in _all_ratings if r.edge_opportunity == EdgeOpportunity.LOW]
    _efficient = [(q, r) for q, r in _all_ratings if r.edge_opportunity == EdgeOpportunity.VERY_LOW]

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric(
        "🟢 Potential Edge",
        len(_high),
        help="No reference market — prices set by retail without professional consensus.",
    )
    mc2.metric(
        "🟡 Model Edge",
        len(_medium),
        help="Reference model exists (NWP weather, polling) but retail participants rarely use it.",
    )
    mc3.metric("🟠 Low Edge", len(_low), help="Professional reference (sports books) — hard to beat.")
    mc4.metric(
        "🔴 Efficient",
        len(_efficient),
        help="Deep liquid reference market (CME FedWatch, crypto exchanges) — arb'd quickly.",
    )

    st.markdown("---")

    # ── Topic efficiency overview ─────────────────────────────────────────────
    st.markdown("#### Market Efficiency by Topic")
    st.caption(
        "Each row shows the dominant backing source and edge level for that topic. "
        "Focus research time on topics near the top of this table."
    )
    topic_df = _topic_efficiency_summary_df(all_shown)
    st.dataframe(
        topic_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Topic": st.column_config.TextColumn("Topic"),
            "Markets": st.column_config.NumberColumn("# Markets", format="%d"),
            "Avg Spread (pp)": st.column_config.NumberColumn("Avg Spread (pp)", format="%.1f"),
            "Reference Market": st.column_config.TextColumn("Reference Market"),
            "Edge Level": st.column_config.TextColumn("Edge Level"),
        },
    )

    st.markdown("---")

    # ── High-edge markets ─────────────────────────────────────────────────────
    st.markdown("#### 🟢 High Edge Potential — No Reference Market")
    st.caption(
        "These markets have **no liquid external reference price**.  "
        "Market makers are setting bid/ask based on gut feel, copying each other, or chasing "
        "social media sentiment — not consulting a professional consensus source.  "
        "Even a basic systematic model (historical base rates, sentiment analysis, domain research) "
        "can generate meaningful edge here."
    )
    if _high:
        df_high = _edge_opportunities_df([q for q, _ in _high])
        st.dataframe(
            df_high,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Title": st.column_config.TextColumn("Market", width="large"),
                "Reference Market": st.column_config.TextColumn("Reference Market"),
                "Edge": st.column_config.TextColumn("Edge"),
                "Spread pp": st.column_config.NumberColumn("Spread (pp)", format="%.2f"),
                "Total Vol": st.column_config.NumberColumn("Total Vol ($)", format="$%,.0f"),
                "Closes": st.column_config.DateColumn("Closes"),
            },
        )
    else:
        st.info("No high-edge markets under current filters.")

    st.markdown("---")

    # ── Model-edge markets ────────────────────────────────────────────────────
    st.markdown("#### 🟡 Model Edge — Reference Exists, Retail Doesn't Use It")
    st.caption(
        "A reference model or data source **exists** for these markets, but most prediction market "
        "participants are **not consulting it**.  "
        "Edge is available if you can access and correctly apply the model:\n\n"
        "- **Weather** → ECMWF/GFS ensemble NWP output vs. retail temperature guesses  \n"
        "- **Politics** → Polling aggregators (Silver Bulletin) vs. vibes-based political takes  \n"
        "- **Minor sports** → Niche lines or props where books are less sharp"
    )
    if _medium:
        df_med = _edge_opportunities_df([q for q, _ in _medium])
        st.dataframe(
            df_med,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Title": st.column_config.TextColumn("Market", width="large"),
                "Reference Market": st.column_config.TextColumn("Reference Market"),
                "Edge": st.column_config.TextColumn("Edge"),
                "Spread pp": st.column_config.NumberColumn("Spread (pp)", format="%.2f"),
                "Total Vol": st.column_config.NumberColumn("Total Vol ($)", format="$%,.0f"),
                "Closes": st.column_config.DateColumn("Closes"),
            },
        )
    else:
        st.info("No model-edge markets under current filters.")

    # ── Efficient-market reminder ─────────────────────────────────────────────
    with st.expander(
        f"🔴 Efficient markets ({len(_efficient)} CME/crypto) and 🟠 Low edge ({len(_low)} sports books) — expand to see"
    ):
        st.caption(
            "**Efficient** (CME FedWatch, crypto exchanges): Deep professional arbitrage closes "
            "any gap within minutes. Do not attempt to find edge here.\n\n"
            "**Low edge** (major sports books): Vegas and FanDuel lines are set by teams of "
            "professional oddsmakers with billions in capital. Prediction market prices closely "
            "track vig-free book probabilities. Very hard to beat systematically."
        )
        if _efficient or _low:
            df_eff = _edge_opportunities_df([q for q, _ in _efficient + _low])
            st.dataframe(df_eff, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — Event Groups
# Browse any event group with 2+ contracts. Auto-renders a term-structure chart
# or threshold chart depending on what the group contains.
# ════════════════════════════════════════════════════════════════════════════════

with tab_groups:
    # Build event group index
    groups: dict[str, list[NormalizedQuote]] = {}
    for q in all_shown:
        if q.event_group and q.event_group != "—":
            groups.setdefault(q.event_group, []).append(q)

    multi = {k: v for k, v in groups.items() if len(v) >= 2}
    multi_sorted = dict(sorted(multi.items(), key=lambda kv: -len(kv[1])))

    if not multi_sorted:
        st.info("No event groups with 2+ contracts found under current filters.")
    else:
        col_list, col_detail = st.columns([1, 3], gap="large")

        with col_list:
            group_keys = list(multi_sorted.keys())
            sel_key = st.selectbox(
                f"Event groups ({len(multi_sorted)})",
                options=group_keys,
                format_func=lambda k: f"{k}  [{len(multi_sorted[k])} contracts]",
                help="Groups are sorted by contract count, largest first.",
            )

        if sel_key:
            gq = multi_sorted[sel_key]
            venues_in_group = sorted({q.venue.capitalize() for q in gq})
            topics_in_group = sorted({q.topic.capitalize() for q in gq if q.topic})

            with col_detail:
                st.markdown(
                    f"**{sel_key}** &nbsp;·&nbsp; "
                    f"{len(gq)} contracts &nbsp;·&nbsp; "
                    f"{'  /  '.join(venues_in_group)} &nbsp;·&nbsp; "
                    f"{'  /  '.join(topics_in_group)}"
                )

            # Contracts table
            st.dataframe(_quotes_to_df(gq), use_container_width=True, hide_index=True)

            # Auto-detect and render chart
            dated = [q for q in gq if q.close_time is not None]
            unique_dates = {q.close_time.date() for q in dated}

            thresh_pts = [(q, _extract_threshold(q.title)) for q in gq]
            thresh_pts_clean = [(q, t) for q, t in thresh_pts if t is not None]

            if len(unique_dates) >= 2:
                # Term structure — split by venue so both lines show
                by_venue: dict[str, list[NormalizedQuote]] = {}
                for q in dated:
                    by_venue.setdefault(q.venue, []).append(q)
                fig = _term_structure_chart(by_venue, f"{sel_key} — Term Structure")
                st.pyplot(fig)
                plt.close(fig)

            elif len(thresh_pts_clean) >= 2:
                fig = _cdf_chart(thresh_pts_clean, f"{sel_key} — Threshold Structure")
                st.pyplot(fig)
                plt.close(fig)

            else:
                st.caption("No date or threshold variation detected — chart not available for this group.")

            # Raw detail expander
            with st.expander("Raw contract detail"):
                for q in sorted(gq, key=lambda q: q.close_time or datetime.min):
                    st.code(
                        f"ID:     {q.market_id}\n"
                        f"Title:  {q.title}\n"
                        f"Venue:  {q.venue}  |  Topic: {q.topic}\n"
                        f"Mid:    {q.prob_mid_or_last:.4f}  "
                        f"Bid: {q.prob_bid:.4f if q.prob_bid else 'n/a'}  "
                        f"Ask: {q.prob_ask:.4f if q.prob_ask else 'n/a'}  "
                        f"Spread: {q.spread * 100:.2f}pp"
                        if q.spread
                        else "Spread: n/a",
                        language="text",
                    )

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — Term Structures
# All detected term structure series across enabled topics.
# Select one → full-width chart with annotated probability path.
# ════════════════════════════════════════════════════════════════════════════════

with tab_term:
    if not term_series:
        st.info(
            "No term structure series detected under current filters.\n\n"
            "Try: lowering liquidity filters, expanding topics, or reducing "
            "the min-contracts-per-series slider."
        )
    else:
        col_list, col_info = st.columns([1, 3], gap="large")

        with col_list:
            ts_labels = [f"{s.event_group}  [{s.venue[:1].upper()}]  ({s.size})" for s in term_series]
            sel_ts = st.selectbox(
                f"Series ({len(term_series)})",
                options=range(len(term_series)),
                format_func=lambda i: ts_labels[i],
            )

        s = term_series[sel_ts]

        with col_info:
            dates_present = [q.close_time for q in s.contracts if q.close_time]
            date_range = (
                f"{min(dates_present).strftime('%b %d')} → {max(dates_present).strftime('%b %d, %Y')}"
                if dates_present
                else "—"
            )
            st.markdown(
                f"**{s.event_group}** &nbsp;·&nbsp; "
                f"{s.venue.capitalize()} &nbsp;·&nbsp; "
                f"{s.topic.value.capitalize()} &nbsp;·&nbsp; "
                f"{s.size} contracts &nbsp;·&nbsp; {date_range}"
            )

        # Chart
        by_venue_ts: dict[str, list[NormalizedQuote]] = {}
        for q in s.contracts:
            by_venue_ts.setdefault(q.venue, []).append(q)
        fig = _term_structure_chart(by_venue_ts, f"{s.event_group} — Term Structure")
        st.pyplot(fig)
        plt.close(fig)

        # Contracts table
        st.dataframe(_quotes_to_df(s.contracts), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — Threshold CDFs
# All detected threshold series. Shows P(X > threshold) vs threshold —
# the market's implied survivor function — with fitted normal overlay
# and residual annotations (red if deviation > 2pp from fit).
# ════════════════════════════════════════════════════════════════════════════════

with tab_cdf:
    if not cdf_series:
        st.info(
            "No threshold CDF series detected under current filters.\n\n"
            "These require 3+ contracts in the same event group with parseable "
            "numeric thresholds in their titles (e.g. 'CPI above 3.0%', "
            "'Temperature above 80°F')."
        )
    else:
        col_list, col_info = st.columns([1, 3], gap="large")

        with col_list:
            cdf_labels = [f"{s.event_group}  [{s.venue[:1].upper()}]  ({s.size})" for s in cdf_series]
            sel_cdf = st.selectbox(
                f"Series ({len(cdf_series)})",
                options=range(len(cdf_series)),
                format_func=lambda i: cdf_labels[i],
            )

        s = cdf_series[sel_cdf]

        with col_info:
            st.markdown(
                f"**{s.event_group}** &nbsp;·&nbsp; "
                f"{s.venue.capitalize()} &nbsp;·&nbsp; "
                f"{s.topic.value.capitalize()} &nbsp;·&nbsp; "
                f"{s.size} contracts"
            )
            st.caption("Chart shows P(X > threshold). Red residual annotations = deviation > 2pp from fitted normal.")

        pts = [(q, _extract_threshold(q.title)) for q in s.contracts]
        pts_clean: list[tuple[NormalizedQuote, float]] = [(q, t) for q, t in pts if t is not None]

        if len(pts_clean) >= 2:
            fig = _cdf_chart(pts_clean, f"{s.event_group} — Implied Survivor Function", fit_normal=True)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.warning("Couldn't extract thresholds from contract titles — chart unavailable.")

        # Contracts table with threshold column injected
        df_cdf = _quotes_to_df(s.contracts)
        thresholds = [_extract_threshold(q.title) for q in s.contracts]
        df_cdf.insert(1, "Threshold", thresholds)
        st.dataframe(df_cdf, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 7 — Oscar 2026
# Model predictions vs Kalshi market prices for all major categories.
# Shows model probability, Kalshi price, edge (pp), and Kelly $ for each nominee.
# ════════════════════════════════════════════════════════════════════════════════

with tab_oscar:
    from src.analysis.oscar.model import CategoryPrediction, kelly_bet_size, run_all_categories

    st.markdown("### 🏆 98th Academy Awards — Prediction Model vs Kalshi Market")
    st.caption(
        "Precursor-correlation model | Scores = ε(0.10 base) + historical correlations | "
        "Per-category temperatures calibrated to match historical win rates | "
        "NOT fitted to 2026 data — this is a prior. Update after PGA (Feb 28), SAG (Mar 1), WGA (Mar 8)."
    )

    oscar_bankroll = float(DashboardConfig.from_env().bankroll)

    col_meta1, col_meta2, col_meta3 = st.columns(3)
    col_meta1.metric("Ceremony", "Mar 15, 2026")
    col_meta2.metric("Host", "Conan O'Brien")
    col_meta3.metric("Bankroll (Kelly sizing)", f"${oscar_bankroll:,.0f}")

    # ── Pending precursors alert ─────────────────────────────────────────────
    st.info(
        "⏳ **Pending precursors** — model will strengthen after these results:\n\n"
        "- **Feb 28** — PGA Awards (Darryl F. Zanuck Award = Best Picture key predictor)\n"
        "- **Mar 1** — SAG Awards (strongest predictor for Lead Actor, Lead Actress, Supporting)\n"
        "- **Mar 8** — WGA Awards (Original & Adapted Screenplay)\n\n"
        "SAG on Mar 1 is especially important. "
        "Categories with many pending precursors show wider probability spreads."
    )

    @st.cache_data(ttl=300, show_spinner=False)
    def _oscar_predictions() -> dict[str, CategoryPrediction]:
        return run_all_categories()

    oscar_preds = _oscar_predictions()

    # ── Executive summary: top edge opportunities ────────────────────────────
    st.markdown("#### Top Edge Opportunities")

    edge_rows = []
    for _slug, cat in oscar_preds.items():
        for r in cat.nominees:
            if r.kalshi_price is not None and r.edge_vs_market is not None:
                kelly = kelly_bet_size(r, oscar_bankroll) or 0.0
                edge_rows.append(
                    {
                        "Category": cat.category_display,
                        "Nominee": r.nominee,
                        "Film": r.film,
                        "Model %": round(r.model_prob * 100, 1),
                        "Market ¢": round((r.kalshi_price or 0) * 100),
                        "Edge pp": round((r.edge_vs_market or 0) * 100, 1),
                        "Kelly $": round(kelly),
                        "Action": (
                            f"BUY YES ({round((r.kalshi_price or 0)*100):.0f}¢)"
                            if (r.edge_vs_market or 0) > 0
                            else f"BUY NO ({100 - round((r.kalshi_price or 0)*100):.0f}¢)"
                        ),
                    }
                )

    if edge_rows:
        df_edge = pd.DataFrame(edge_rows)
        df_edge = df_edge[abs(df_edge["Edge pp"]) >= 3].copy()
        df_edge = df_edge.sort_values("Edge pp", key=abs, ascending=False).reset_index(drop=True)

        def _color_edge(val: float) -> str:
            if val > 5:
                return "color: #22c55e"  # green
            if val > 2:
                return "color: #86efac"
            if val < -5:
                return "color: #ef4444"  # red
            if val < -2:
                return "color: #fca5a5"
            return ""

        styled = df_edge.style.map(_color_edge, subset=["Edge pp"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("No edge opportunities ≥ 3pp found.")

    # ── Per-category detail ──────────────────────────────────────────────────
    st.markdown("#### Category Detail")

    CATEGORY_ORDER = [
        "best_picture",
        "best_director",
        "best_actor",
        "best_actress",
        "best_supporting_actor",
        "best_supporting_actress",
        "best_original_screenplay",
        "best_adapted_screenplay",
    ]

    for slug in CATEGORY_ORDER:
        cat = oscar_preds.get(slug)
        if cat is None:
            continue

        with st.expander(f"**{cat.category_display}**", expanded=(slug == "best_picture")):
            if cat.pending_precursors:
                st.caption(f"⏳ Pending: {', '.join(cat.pending_precursors)}")

            # Build per-category DataFrame
            cat_rows = []
            for r in cat.nominees:
                kelly = kelly_bet_size(r, oscar_bankroll)
                cat_rows.append(
                    {
                        "Nominee": r.nominee,
                        "Film": r.film,
                        "Model %": round(r.model_prob * 100, 1),
                        "Market ¢": round((r.kalshi_price or 0) * 100) if r.kalshi_price is not None else None,
                        "Gold Derby %": round((r.gold_derby_prob or 0) * 100, 1) if r.gold_derby_prob else None,
                        "Edge pp": round((r.edge_vs_market or 0) * 100, 1) if r.edge_vs_market is not None else None,
                        "Kelly $": round(kelly) if kelly else None,
                        "Precursors Won": ", ".join(r.precursors_won) if r.precursors_won else "—",
                    }
                )
            df_cat = pd.DataFrame(cat_rows)

            # Probability bar chart inline
            fig_cat, ax_cat = plt.subplots(figsize=(7, max(2.0, len(cat.nominees) * 0.45)))
            names = [r.nominee for r in cat.nominees]
            probs = [r.model_prob * 100 for r in cat.nominees]
            market_probs = [(r.kalshi_price or 0) * 100 for r in cat.nominees]
            y_pos = range(len(names))
            ax_cat.barh(y_pos, probs, color="#3b82f6", alpha=0.85, label="Model", height=0.4, align="center")
            ax_cat.barh(
                [y + 0.42 for y in y_pos],
                market_probs,
                color="#f59e0b",
                alpha=0.65,
                label="Kalshi market",
                height=0.4,
                align="center",
            )
            ax_cat.set_yticks([y + 0.21 for y in y_pos])
            ax_cat.set_yticklabels(names, fontsize=9)
            ax_cat.set_xlabel("Probability (%)")
            ax_cat.set_xlim(0, 105)
            ax_cat.legend(fontsize=8, loc="lower right")
            ax_cat.spines["top"].set_visible(False)
            ax_cat.spines["right"].set_visible(False)
            fig_cat.tight_layout()
            st.pyplot(fig_cat)
            plt.close(fig_cat)

            st.dataframe(df_cat, use_container_width=True, hide_index=True)

            # Top pick annotation
            top = cat.top_pick
            best_edge = cat.best_edge_opportunity
            col_top, col_best = st.columns(2)
            col_top.metric("Model top pick", top.nominee, f"{top.model_prob*100:.1f}% model")
            if best_edge and best_edge.edge_vs_market is not None and abs(best_edge.edge_vs_market) > 0.02:
                edge_pp = best_edge.edge_vs_market * 100
                action = "BUY YES" if edge_pp > 0 else "BUY NO"
                col_best.metric(
                    f"Best edge: {action} {best_edge.nominee}",
                    f"{edge_pp:+.1f}pp",
                    f"model {best_edge.model_prob*100:.1f}% vs market {(best_edge.kalshi_price or 0)*100:.0f}¢",
                )
