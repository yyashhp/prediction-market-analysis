# CLAUDE.md — Prediction Market Relative Value Dashboard

> **Purpose:** Single source of truth for every new Claude session on this repo.
> Captures architecture, goals, key decisions, anti-patterns, and orientation tips.
> **Update this file whenever a meaningful decision is made or a mistake is discovered.**
> See `docs/REQUIREMENTS.md` and `docs/DESIGN.md` for the full spec.

---

## 1. What We're Building (The Short Version)

A **live, topic-organized relative value (RV) dashboard** that acts like a mock market maker's
monitor across Kalshi and Polymarket prediction markets. It:

1. Fetches live market data from both venues
2. Groups contracts by topic (Weather, Sports, Macro/Fed, Crypto, Politics)
3. For each topic, surfaces relative mispricings by comparing:
   - **Same contract cross-venue** (Kalshi vs Polymarket — pure arb)
   - **Term structure contracts** (same event, different expiry dates — calendar spread)
   - **Threshold contracts** (same event, different thresholds — implied CDF consistency)
4. Scores each edge by size (in spread units), Kelly-adjusted size, and liquidity
5. Filters out illiquid noise; only shows contracts meeting minimum thresholds
6. Helps a small-bankroll operator find and prioritize the best selective-take opportunities

This is **not** a market making system (adverse selection + no maker rebates = bad for small bankroll).
It is a **selective taker / pair-trade** system, finding spots where the market is wrong relative
to itself or a reference model.

---

## 2. Core Conceptual Framework

### Binary Options, Not Vanilla Options
Each prediction market contract is a digital/binary option: pays $1 at expiry if condition met.
The standard options delta-hedging framework **does not apply** — there is no tradable underlying.

### What "Vol-Aware" Means Here
Vol-awareness ≠ Greek hedging. It means: *how uncertain is the probability estimate, and how do
related contracts constrain each other?* Three structural analogs replace the vol surface:

| Analog | Example | Edge Type |
|--------|---------|-----------|
| **Term structure** | "Fed cuts ≥25bps in March" vs "in May" vs "in June" | Calendar spread — probabilities must be monotone (P(cut by May) ≥ P(cut by March)) |
| **Strike structure** | "CPI > 2.5%" vs "> 3.0%" vs "> 3.5%" | Implied CDF — fit a parametric distribution (e.g. normal); contracts deviating from curve = RV trade |
| **Cross-venue** | Same contract on Kalshi and Polymarket | Pure arb if spread > round-trip transaction cost |

### Topic Feasibility Ranking (Agreed Priority Order)

| Topic | Feasibility | Reason | Strategy |
|-------|-------------|--------|---------|
| **Weather** | Highest | Physical variable; pro models (ECMWF/GFS/NWS) vs retail guessers; genuine calibration edge | Selective taker only (illiquid, wide spreads — edge must clear spread) |
| **Sports** | High | Deep liquid reference market (Vegas/FanDuel); bracket no-arb constraints | Cross-venue arb + bracket completeness arb |
| **Macro/Fed** | Medium | CME FedWatch gives exact implied probs from futures; some residual in multi-cut conditionals | Term structure arb against CME path model |
| **Crypto** | Low | Perp markets, options, on-chain analytics = efficient; skip unless unique alpha | Skip |
| **Politics** | Avoid | High adverse selection; insider risk; not systematic | Do not trade |

### Why Not Market Making?
- Severe adverse selection (informed trader hits your quote when you're wrong → lose full $1/contract)
- Inventory management ties up 2× capital for 1× risk exposure
- No maker rebates on Kalshi/Polymarket (unlike exchange options)
- Queue priority disadvantage for small participants
- **Conclusion:** Be a selective taker, not a maker

### The Right Strategy for Small Bankroll

| Approach | Capital Efficiency | Edge Type | Complexity |
|----------|-------------------|-----------|------------|
| Selective taker (model vs market) | High | Calibration edge | Medium |
| Cross-venue arb (Kalshi ↔ Poly) | Very High | Structural | Low |
| Within-topic pair trade | High (correlated risk) | Distribution consistency | High |
| Bracket/tournament completeness | High | No-arb constraint | Medium |
| Market making | Low | Spread capture | Very High ← **avoid** |

---

## 3. Existing Codebase Architecture

### Entry Point
- `main.py` — CLI: `analyze`, `index`, `package`, `dashboard` (terminal once-off)
- `make analyze` → interactive menu; `uv run main.py analyze <name>` → specific analysis
- **`make dashboard`** → launches the Streamlit research dashboard at `localhost:8501`

### Source Tree (Pre-Existing)
```
src/
  analysis/
    kalshi/          # ~15 batch analyses (win rate, EV, maker/taker, calibration, mispricing, etc.)
    polymarket/      # 3 batch analyses (volume over time, trades over time, win rate by price)
    comparison/      # 1 cross-platform animated analysis (win_rate_by_price_animated)
  indexers/
    kalshi/          # Kalshi API client (kalshi-python SDK) + market/trade indexers
    polymarket/      # Polymarket API + Polygon blockchain indexers (CTF Exchange, legacy FPMM, blocks)
  common/
    analysis.py      # Analysis base class + AnalysisOutput dataclass
    indexer.py       # Indexer base class
    client.py        # HTTP client base (httpx)
    storage.py       # Parquet storage (pyarrow)
    interfaces/chart.py  # ChartConfig for JSON chart export
    util/            # package_data, string utils
```

### New Modules (Complete)
```
src/
  rv/                # Relative value core: normalizer, matcher, edge calc, Kelly
  live/              # Live API polling layer (KalshiFeed, PolymarketFeed, FeedManager)
  dashboard/
    streamlit_app.py # PRIMARY UI — Streamlit research dashboard (make dashboard)
    app.py           # FeedManager wiring + terminal once-off runner
    renderer.py      # Terminal text renderer (secondary, for CLI --once)
    config.py        # DashboardConfig (env-based)
```

### Data Layout (Historical Parquet — For Backtesting/Reference)
```
data/
  kalshi/   markets/*.parquet  trades/*.parquet
  polymarket/  markets/*.parquet  trades/*.parquet  blocks/*.parquet  legacy_trades/*.parquet
output/      — analysis outputs (PNG, PDF, CSV, JSON)
```

### Key Schema Notes
**Kalshi:** Prices in **cents** (int 1–99); `no_price = 100 - yes_price`; `yes_bid/ask`, `no_bid/ask` nullable;
`taker_side` = `'yes'`|`'no'`; `result` = `'yes'`|`'no'`|`''`; `ticker` → market, `event_ticker` → event group.

**Polymarket:** Prices in **decimals** (float 0–1); multiply ×100 for cents. CTF trades: raw
`OrderFilled` events (maker_amount/taker_amount in 6-decimal USDC). Resolution: `closed=True` +
final `outcome_prices` ≈ 0.99/0.01 → winner. Block → timestamp join for time analysis.

### Dependencies Already Available
**Live access:** `kalshi-python`, `polymarket-py`, `httpx`, `web3`, `tenacity`
**Analysis:** `duckdb`, `pandas`, `matplotlib`, `scipy`, `tqdm`, `brokenaxes`, `squarify`
**Dashboard:** `streamlit>=1.35`
**Dev:** `pytest`, `ruff` (line-length=120, py39, isort, pyflakes, bugbear)
**Infra:** `pyarrow`, `python-dotenv`, `cryptography`, `imageio`

---

## 4. Development Rules

### Git
- **Branch:** `claude/prediction-market-relative-value-FXsMY` — ALL work here
- **Push:** `git push -u origin claude/prediction-market-relative-value-FXsMY`
- Never push to `main` or `master`
- Retry push up to 4× on network failure: 2s, 4s, 8s, 16s backoff

### Code Style
- Python 3.9+; `from __future__ import annotations` at top of every file
- Type hints throughout; prefer explicit types over `Any`
- `duckdb` for Parquet SQL (don't load entire files into pandas memory)
- `ruff check .` and `ruff format .` before committing
- Line length: 120 chars

### Running Things
```bash
uv sync                              # install deps
make dashboard                       # launch Streamlit dashboard → localhost:8501
make analyze                         # interactive analysis menu
uv run main.py analyze <name>        # run specific batch analysis
make index                           # interactive indexer menu
uv run pytest tests/                 # run tests
make setup                           # download 36GiB historical dataset
```

### Testing
- Tests in `tests/`; use `pytest`; existing tests cover compile, instantiation, save pipeline
- New `rv/`/`live/`/`dashboard/` modules need unit tests with mocked API responses

---

## 5. Mistakes to Avoid (Running Log)

> Add every mistake here the moment it's caught. Never repeat a listed mistake.

| # | Mistake | Correct Approach |
|---|---------|-----------------|
| 1 | `categories.py` `get_group()` uses substring matching (`pattern in string`), so "EC" matches inside "FEDDECISION" → classified as Electoral College instead of Finance/Fed | Built `_get_group_prefix()` in `classifier.py` that extracts the alphabetic prefix and does longest-prefix-first matching. Never use `get_group()` directly for the RV system. |
| 2 | Polymarket classifier: "win" keyword in Sports regex triggered on political/entertainment questions ("win the Senate", "win the Oscar") | Reordered `_POLYMARKET_PATTERNS` so Politics and Entertainment are checked before Sports. Removed generic "win the" from Sports pattern; kept only specific sports terms. |
| 3 | Float comparison `assert q.spread == 0.02` fails due to floating point precision (0.57 - 0.55 = 0.01999...9907) | Always use `abs(a - b) < 1e-10` or `pytest.approx()` for float comparisons. Never `==` on floats. |
| 4 | `api.elections.kalshi.com` is Kalshi's elections-only subdomain — returns almost exclusively political markets. Default topic filter `["weather", "sports", "macro"]` filtered all of them → 0 Kalshi shown. | Changed dashboard default topics to ALL topics. The research surface should show everything by default; the analyst narrows from there. The API limitation (elections-only URL) is a known constraint. |
| 5 | Polymarket `Market.from_dict` dropped `bestBid`, `bestAsk`, `spread`, `volume24Hr` — gamma API returns them but the model didn't capture them. Feed then reconstructed a stripped dict, so `from_polymarket` never saw bid/ask/spread/vol24h. | Added `best_bid`, `best_ask`, `spread`, `volume_24h` fields to `src/indexers/polymarket/models.py`. Updated `PolymarketFeed` to pass them through. Updated `from_polymarket` to use them. |
| 6 | Polymarket `event_group` set to the market's own unique `slug` → every market is a group of 1 → no event groups, no series detected. | Added `_polymarket_group_slug()` in `normalizer.py`: strips trailing month names and 4-digit years from the slug, so related series contracts (e.g. "fed-cut-march-2026", "fed-cut-april-2026") share the group key "fed-cut". |
| 7 | Polymarket OI always 0 — true open interest is not in the gamma API. | Use `liquidity` ($) as an OI proxy. It's not identical but both measure depth. Dashboard tooltip now clarifies: "Kalshi: OI (contracts). Polymarket: liquidity ($)." |

---

## 6. Key Decisions From Prior Conversations

1. **No market making** — adverse selection + no rebates + queue disadvantage kills small-bankroll maker strategies
2. **Selective taker only** — enter when model disagrees with market by more than the bid-ask spread
3. **Cross-venue arb is NOT the primary focus** — it is one lens among many; the dashboard is a research surface first
4. **Dashboard goal = show market structure, not alert on trades** — show term structure curves, threshold CDFs, contract series in normalized/comparable form; let the analyst spot the patterns like an institutional quant desk
5. **Weather is the most tractable alpha source** — retail participants not using ECMWF/GFS ensemble forecasts; physical variable is directly measurable
6. **Sports: use Vegas/FanDuel as the reference model** — deep, liquid, and accurate
7. **Macro/Fed: use CME FedWatch** — gives exact implied probabilities from Fed funds futures; fit Markov path model for conditional probabilities
8. **Skip Crypto** — too many sophisticated participants
9. **Avoid Politics** — high adverse selection, insider risk, not systematic
10. **Liquidity filters are mandatory** — without them the dashboard is noise
11. **Kelly sizing with hard caps** — size = f(edge, spread, bankroll); hard cap per contract/topic/venue
12. **Dashboard is Streamlit** — browser-based, `localhost:8501`, wide layout, manual refresh + filter controls
13. **Contracts must share terms within series** — compare "Fed rate decision" across months (same terms, different expiry), never apples-to-oranges
14. **Don't mess with weirdly-termed contracts** — stick to standardized series even if oddball contracts have edge (execution risk too high)
15. **Feed pagination is capped** — Kalshi max 5 pages (1000 markets), Polymarket max 5 pages (2500 markets), with inter-page sleep to avoid 429s; both fetched in parallel via ThreadPoolExecutor
16. **Edge definition is not binary** — every contract/series carries raw metrics (bid/ask/mid/spread/volume/OI/close_time); the `metadata` dict on Edge objects holds fitted distribution params, residuals, etc. The dashboard surfaces all of this, not just a pass/fail flag

---

## 7. Open Questions / Decisions Needed

1. ~~**Dashboard technology:**~~ **Resolved: Streamlit.** `src/dashboard/streamlit_app.py`, `make dashboard`.
2. **Market matching:** Curated mapping file (manual, precise) vs NLP similarity (automated, fuzzy) vs hybrid? Currently using fuzzy SequenceMatcher + same-topic + date proximity. Cross-venue match quality is low — `config/matched_pairs.json` not yet populated. **Next: build curated pairs for highest-volume overlapping series.**
3. **Weather reference model source:** NWS API (free, US-only) vs ECMWF API (subscription, global)?
4. **Update frequency:** How often to poll APIs? (Leaning: 60s for markets, 30s for active positions). Manual refresh implemented for now.
5. **Liquidity filter defaults:** Sidebar sliders default to 0 (show everything). Good for exploration. Tighten defaults once you know which series matter.
6. **Bankroll for Kelly:** Defaults to $10,000 via `RV_BANKROLL` env var. Set in `.env`.
7. **Backtest mode:** Should the RV system also run historically against stored Parquet data?
8. **Reference model wiring:** `model_vs_market` edge type exists in `edge.py` but nothing passes `reference_probs` yet. NWS weather, CME FedWatch, Vegas odds all need a fetcher module to wire in.

---

## 8. Reference Docs
- `docs/REQUIREMENTS.md` — formal functional + non-functional requirements
- `docs/DESIGN.md` — system architecture, module breakdown, data flow
- `docs/ANALYSIS.md` — guide for writing batch analysis scripts (existing)
- `docs/SCHEMAS.md` — Parquet data schemas (existing)

---

*Last updated: 2026-02-23 — Dashboard data quality fixes: Polymarket bid/ask/spread/vol24h now populated from gamma API fields; OI proxied by liquidity; event_group uses slug-stripping for series detection; default topic filter changed to ALL topics so Kalshi elections-API markets appear; Market Browser no longer shows ID/Event Group columns.*
