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
- `main.py` — CLI: `analyze`, `index`, `package`
- `make analyze` → interactive menu; `uv run main.py analyze <name>` → specific analysis

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

### New Modules (Being Built — See DESIGN.md)
```
src/
  rv/                # Relative value core: normalizer, matcher, edge calc, Kelly
  live/              # Live API polling layer
  dashboard/         # Live dashboard UI
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
| 1 | _(none yet — first session; populate as work proceeds)_ | — |

---

## 6. Key Decisions From Prior Conversations

1. **No market making** — adverse selection + no rebates + queue disadvantage kills small-bankroll maker strategies
2. **Selective taker only** — enter when model disagrees with market by more than the bid-ask spread
3. **Cross-venue arb is highest capital efficiency** — simultaneous Kalshi + Polymarket on same event
4. **Weather is the most tractable alpha source** — retail participants not using ECMWF/GFS ensemble forecasts; physical variable is directly measurable
5. **Sports: use Vegas/FanDuel as the reference model** — deep, liquid, and accurate
6. **Macro/Fed: use CME FedWatch** — gives exact implied probabilities from Fed funds futures; fit Markov path model for conditional probabilities
7. **Skip Crypto** — too many sophisticated participants
8. **Avoid Politics** — high adverse selection, insider risk, not systematic
9. **Liquidity filters are mandatory** — without them the dashboard is noise
10. **Kelly sizing with hard caps** — size = f(edge, spread, bankroll); hard cap per contract/topic/venue
11. **Dashboard is the product** — live, not batch; per-topic panels; auto-refreshing
12. **Contracts must share terms within series** — compare "Fed rate decision" across months (same terms, different expiry), never apples-to-oranges
13. **Don't mess with weirdly-termed contracts** — stick to standardized series even if oddball contracts have edge (execution risk too high)

---

## 7. Open Questions / Decisions Needed

1. **Dashboard technology:** Streamlit (simplest) vs Textual (terminal) vs Dash (richest)?
2. **Market matching:** Curated mapping file (manual, precise) vs NLP similarity (automated, fuzzy) vs hybrid?
3. **Weather reference model source:** NWS API (free, US-only) vs ECMWF API (subscription, global)?
4. **Update frequency:** How often to poll APIs? (Leaning: 60s for markets, 30s for active positions)
5. **Liquidity filter defaults:** Min daily volume ($500?), max bid-ask spread (10¢?), min OI (200 contracts?)
6. **Bankroll for Kelly:** What total bankroll to parameterize against?
7. **Backtest mode:** Should the RV system also run historically against stored Parquet data?

---

## 8. Reference Docs
- `docs/REQUIREMENTS.md` — formal functional + non-functional requirements
- `docs/DESIGN.md` — system architecture, module breakdown, data flow
- `docs/ANALYSIS.md` — guide for writing batch analysis scripts (existing)
- `docs/SCHEMAS.md` — Parquet data schemas (existing)

---

*Last updated: 2026-02-21 — Full prior chat context integrated.*
