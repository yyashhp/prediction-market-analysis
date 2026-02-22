"""Terminal-based dashboard renderer using print formatting.

Displays edge scan results organized by topic with color-coded
edge magnitudes. Uses basic ANSI colors for terminal compatibility.
"""

from __future__ import annotations

import os

from src.live.feed_manager import EdgeScanResult, MarketSnapshot
from src.rv.classifier import Topic
from src.rv.edge import Edge

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _color_edge(spread_ratio: float) -> str:
    """Color code based on edge quality."""
    if spread_ratio >= 3.0:
        return GREEN
    elif spread_ratio >= 2.0:
        return YELLOW
    else:
        return DIM


def _color_grade(grade: str) -> str:
    """Color code liquidity grade."""
    if grade == "A":
        return GREEN
    elif grade == "B":
        return YELLOW
    else:
        return RED


def _truncate(s: str, max_len: int = 40) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def render_header(snapshot: MarketSnapshot, config_bankroll: float) -> str:
    """Render the dashboard header bar."""
    lines = []
    lines.append(f"\n{BOLD}{'=' * 90}{RESET}")
    lines.append(
        f"{BOLD}{CYAN}  PREDICTION MARKET RV DASHBOARD{RESET}"
        f"  {DIM}|  {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        f"  |  Bankroll: ${config_bankroll:,.0f}{RESET}"
    )
    lines.append(
        f"  {DIM}Kalshi: {len(snapshot.kalshi_quotes)} markets  |  "
        f"Polymarket: {len(snapshot.polymarket_quotes)} markets  |  "
        f"Fetch: {snapshot.fetch_duration_seconds:.1f}s{RESET}"
    )
    lines.append(f"{BOLD}{'=' * 90}{RESET}")
    return "\n".join(lines)


def render_summary(result: EdgeScanResult) -> str:
    """Render the summary bar."""
    actionable = len(result.actionable_edges)
    total = len(result.edges)
    total_kelly = sum(e.kelly_size_usd for e in result.edges)

    lines = []
    lines.append(
        f"  {BOLD}Edges:{RESET} {total} found, "
        f"{GREEN}{actionable} actionable{RESET} (>= 2 spreads)  |  "
        f"Suggested exposure: ${total_kelly:,.0f}  |  "
        f"Scan: {result.scan_duration_seconds:.2f}s  |  "
        f"Filtered: {result.filtered_quotes}/{result.total_quotes} quotes"
    )
    return "\n".join(lines)


def render_edge_row(edge: Edge, index: int) -> str:
    """Render a single edge as a formatted row."""
    color = _color_edge(edge.spread_ratio)
    grade_color = _color_grade(edge.liquidity_grade)

    # Get contract identifiers
    contract_ids = ", ".join(c.market_id for c in edge.contracts[:2])
    contract_ids = _truncate(contract_ids, 30)

    edge_type_short = {
        "cross_venue": "X-Venue",
        "term_structure": "TermStr",
        "threshold_cdf": "ThreshCDF",
        "model_vs_market": "Model",
    }.get(edge.edge_type, edge.edge_type[:8])

    return (
        f"  {color}{index:>3}. "
        f"[{edge_type_short:<9}] "
        f"{_truncate(edge.direction, 50):<52} "
        f"{edge.magnitude_pp:>5.1f}pp  "
        f"{edge.spread_ratio:>4.1f}x  "
        f"{grade_color}{edge.liquidity_grade}{RESET}  "
        f"${edge.kelly_size_usd:>7,.0f}  "
        f"{DIM}{contract_ids}{RESET}"
    )


def render_topic_panel(topic: Topic, edges: list[Edge]) -> str:
    """Render a topic panel with its edges."""
    topic_display = {
        Topic.WEATHER: "WEATHER",
        Topic.SPORTS: "SPORTS",
        Topic.MACRO: "MACRO / FED",
        Topic.CRYPTO: "CRYPTO",
        Topic.POLITICS: "POLITICS",
        Topic.ENTERTAINMENT: "ENTERTAINMENT",
        Topic.OTHER: "OTHER",
    }.get(topic, topic.value.upper())

    lines = []
    lines.append(f"\n  {BOLD}{CYAN}--- {topic_display} ---{RESET}")

    if not edges:
        lines.append(f"  {DIM}(no edges found){RESET}")
        return "\n".join(lines)

    # Column headers
    lines.append(
        f"  {DIM}{'#':>3}  {'Type':<11} {'Direction':<52} {'Edge':>5}  "
        f"{'Ratio':>5}  {'Liq':>1}  {'Kelly $':>8}  {'Contracts'}{RESET}"
    )

    for i, edge in enumerate(edges, 1):
        lines.append(render_edge_row(edge, i))

    return "\n".join(lines)


def render_dashboard(
    snapshot: MarketSnapshot,
    result: EdgeScanResult,
    enabled_topics: list[Topic],
    bankroll: float,
) -> str:
    """Render the full dashboard output."""
    parts = []
    parts.append(render_header(snapshot, bankroll))
    parts.append(render_summary(result))

    for topic in enabled_topics:
        topic_edges = result.edges_by_topic(topic)
        parts.append(render_topic_panel(topic, topic_edges))

    # Footer
    parts.append(f"\n  {DIM}Press Ctrl+C to exit. Auto-refreshes every cycle.{RESET}\n")

    return "\n".join(parts)


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")
