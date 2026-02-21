# Requirements Specification — Prediction Market RV Dashboard

## 1. Problem Statement

A small-bankroll operator wants to systematically identify and exploit relative mispricings
across prediction market contracts on Kalshi and Polymarket. There is no single "underlying"
to delta-hedge against, so the system must detect edges structurally: cross-venue arbitrage,
term structure monotonicity violations, and implied CDF inconsistencies within a topic.

The system must surface only actionable edges — filtered by liquidity, sized by Kelly criterion,
and organized by topic so the operator can focus attention on the most tractable categories.

---

## 2. Functional Requirements

### FR-1: Live Market Data Ingestion

| ID | Requirement |
|----|-------------|
| FR-1.1 | Poll Kalshi API for all active markets and current quotes (bid, ask, last, volume, OI) |
| FR-1.2 | Poll Polymarket API for all active markets and current outcome prices, volume, liquidity |
| FR-1.3 | Normalize all prices to a common probability space (0–1 float, or 0–100 integer cents) |
| FR-1.4 | Refresh data on a configurable interval (default: 60 seconds) |
| FR-1.5 | Handle API rate limits gracefully with exponential backoff (via `tenacity`) |
| FR-1.6 | Cache market metadata (title, event group, resolution date) to avoid redundant fetches |

### FR-2: Topic Classification

| ID | Requirement |
|----|-------------|
| FR-2.1 | Classify every market into one of: Weather, Sports, Macro/Fed, Crypto, Politics, Other |
| FR-2.2 | Use Kalshi `event_ticker` prefix taxonomy as primary classifier (existing `categories.py` util) |
| FR-2.3 | For Polymarket, classify by keyword matching on `question` field + curated slug mappings |
| FR-2.4 | Support a curated override file (`config/topic_overrides.json`) for manual reclassification |
| FR-2.5 | Expose per-topic enable/disable flag (default: Weather + Sports + Macro enabled) |

### FR-3: Market Matching (Cross-Venue Pairing)

| ID | Requirement |
|----|-------------|
| FR-3.1 | Match Kalshi and Polymarket markets that cover the same real-world event and outcome |
| FR-3.2 | Matching criteria: (a) same topic, (b) compatible resolution dates, (c) equivalent outcome terms |
| FR-3.3 | Support a curated pairs file (`config/matched_pairs.json`) for known high-priority pairs |
| FR-3.4 | Optionally support fuzzy text similarity as a fallback for un-curated markets |
| FR-3.5 | Output a confidence score (high/medium/low) for each match |
| FR-3.6 | Never auto-match "weirdly-termed" or non-standard contracts — skip them |

### FR-4: Contract Series Detection (Within-Topic Structure)

| ID | Requirement |
|----|-------------|
| FR-4.1 | Detect **term structure series**: contracts on the same event with different expiry dates (e.g., "Fed cut by March" / "by May" / "by June") |
| FR-4.2 | Detect **threshold series**: contracts on the same metric with different thresholds (e.g., "CPI > 2.5%" / "> 3.0%" / "> 3.5%") |
| FR-4.3 | For term structure: enforce monotonicity constraint (P(event by T₂) ≥ P(event by T₁) for T₂ > T₁) |
| FR-4.4 | For threshold series: fit a parametric distribution (normal, log-normal) to implied CDF; compute residuals per contract |
| FR-4.5 | Flag any contract that violates structural constraints as a candidate RV trade |

### FR-5: Edge Calculation

| ID | Requirement |
|----|-------------|
| FR-5.1 | **Cross-venue edge:** `abs(kalshi_mid - polymarket_mid)` adjusted for bid-ask on both sides |
| FR-5.2 | **Term structure edge:** magnitude of monotonicity violation in probability points |
| FR-5.3 | **Threshold/CDF edge:** residual from fitted parametric distribution in probability points |
| FR-5.4 | **Model-vs-market edge:** difference between external reference model (NWS, CME FedWatch, Vegas) and market mid |
| FR-5.5 | Express all edges in two units: (a) raw probability points, (b) number of bid-ask spreads ("edge/spread ratio") |
| FR-5.6 | Minimum edge threshold filter: only surface edges > N probability points (configurable, default: 3pp) |

### FR-6: Liquidity Filtering

| ID | Requirement |
|----|-------------|
| FR-6.1 | Filter out contracts below configurable liquidity thresholds |
| FR-6.2 | Default thresholds (configurable): min 24h volume $500, max bid-ask spread 10¢, min OI 200 contracts |
| FR-6.3 | Display liquidity grade per contract (A/B/C based on volume + spread + OI) |
| FR-6.4 | All thresholds independently configurable via config file or dashboard UI |

### FR-7: Position Sizing (Kelly Criterion)

| ID | Requirement |
|----|-------------|
| FR-7.1 | Given edge magnitude and bid-ask spread, compute Kelly fraction of bankroll to deploy |
| FR-7.2 | Apply fractional Kelly (default: half-Kelly for safety) |
| FR-7.3 | Enforce hard caps: max per-contract, per-topic, per-venue, and total portfolio exposure |
| FR-7.4 | Accept total bankroll as a configurable parameter |
| FR-7.5 | Display suggested position size alongside each edge in the dashboard |

### FR-8: Dashboard Display

| ID | Requirement |
|----|-------------|
| FR-8.1 | Organize display into per-topic panels (tabs or sections) |
| FR-8.2 | Each panel shows: all active contracts in that topic, sorted by edge magnitude descending |
| FR-8.3 | Per contract row: market title, venue(s), implied probability (mid/bid/ask), edge (pp), edge/spread ratio, liquidity grade, Kelly-suggested size |
| FR-8.4 | For structured topics (term structure, threshold): show the fitted curve + residual visualization |
| FR-8.5 | For cross-venue pairs: show both venue prices side-by-side with spread highlighted |
| FR-8.6 | Auto-refresh at the polling interval (FR-1.4) |
| FR-8.7 | Summary bar: total edges found, average edge size, total capital deployed suggestion |
| FR-8.8 | Color coding: green for edges > 2 spreads, yellow for 1–2 spreads, gray for < 1 spread |

### FR-9: External Reference Models

| ID | Requirement |
|----|-------------|
| FR-9.1 | **Weather:** Fetch probability forecasts from NWS API (free, US) for temperature/precip thresholds |
| FR-9.2 | **Macro/Fed:** Fetch CME FedWatch implied probabilities for rate decisions |
| FR-9.3 | **Sports:** Fetch Vegas/consensus odds from a public odds API as reference model |
| FR-9.4 | Reference model values displayed alongside market prices for model-vs-market edge calculation |
| FR-9.5 | Reference model fetch frequency: configurable (default: 5 minutes for weather, 15 min for macro, 60s for sports during live events) |

---

## 3. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | **Latency:** Dashboard must render within 2 seconds of data refresh completing |
| NFR-2 | **Reliability:** Graceful degradation if one venue API is down (show the other) |
| NFR-3 | **Memory:** Must run on a machine with 4GB RAM (no loading 36GiB dataset into memory) |
| NFR-4 | **Security:** API keys stored in `.env`, never committed to git; `.env` in `.gitignore` |
| NFR-5 | **Modularity:** Each component (feed, matcher, edge calc, Kelly, dashboard) independently testable |
| NFR-6 | **Extensibility:** Adding a new topic or reference model should not require changing core logic |
| NFR-7 | **Python 3.9+** compatibility; managed by `uv` |
| NFR-8 | **Code quality:** `ruff` clean; type hints everywhere; `from __future__ import annotations` |

---

## 4. Out of Scope (Explicit Non-Goals)

1. **Automated trade execution** — this is a monitoring/decision-support system, not an execution engine (yet)
2. **Market making / passive quoting** — unsuitable for small bankroll (see CLAUDE.md §2)
3. **Weirdly-termed or non-standard contracts** — too much execution risk; skip
4. **Crypto topic** — too efficient; skip unless unique alpha identified
5. **Politics topic** — high adverse selection; avoid
6. **Historical backtesting framework** — may be added later but not in v1 scope
7. **Mobile app or hosted web service** — local dashboard only

---

## 5. Acceptance Criteria (Definition of Done)

1. Dashboard launches with `uv run main.py dashboard` (or equivalent)
2. Kalshi and Polymarket markets load and refresh on interval
3. Markets classified into topics; topic panels render correctly
4. At least one cross-venue pair detected and edge computed for a live market
5. At least one term structure series detected with monotonicity check
6. Liquidity filters applied; illiquid contracts hidden by default
7. Kelly sizing displayed per edge
8. All new modules have unit tests passing (`uv run pytest tests/`)
9. `ruff check .` and `ruff format .` pass cleanly
10. CLAUDE.md updated with any new decisions or mistakes discovered during implementation
