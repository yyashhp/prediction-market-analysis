# CLAUDE.md — Prediction Market Relative Value Analysis

> **Purpose:** This file is the single source of truth for any new Claude session working on this repository.
> It captures architecture, goals, decisions, mistakes to avoid, and orientation tips.
> **Update this file whenever a meaningful decision is made or a mistake is discovered.**

---

## 1. Project Overview

**Repo:** `prediction-market-analysis`
**Branch for active development:** `claude/prediction-market-relative-value-FXsMY`

A research framework for analyzing prediction market data (Kalshi + Polymarket).
The existing codebase provides:
- Pre-collected datasets (~36 GiB compressed) stored as Parquet files
- Data collection indexers (Kalshi API, Polymarket blockchain)
- An extensible `Analysis` base class framework for generating figures/statistics

The **new goal** being built on this branch is a **prediction market relative value (RV) edge-capturing structure**: identifying and quantifying pricing discrepancies between Kalshi and Polymarket markets that cover the same underlying event, and building analytical tools to surface, rank, and track those edges.

---

## 2. Codebase Architecture

### Entry Point
- `main.py` — CLI with three commands: `analyze`, `index`, `package`

### Source Tree
```
src/
  analysis/
    kalshi/          # Kalshi-specific analyses (win rate, EV, maker/taker, calibration, etc.)
    polymarket/      # Polymarket-specific analyses (volume, win rate)
    comparison/      # Cross-platform analyses (currently: win_rate_by_price_animated)
  indexers/
    kalshi/          # Kalshi API client + market/trade indexers
    polymarket/      # Polymarket API + blockchain indexers (CTF Exchange & legacy FPMM)
  common/
    analysis.py      # Analysis base class + AnalysisOutput dataclass
    indexer.py       # Indexer base class
    client.py        # HTTP client base
    storage.py       # Parquet storage utilities
    interfaces/
      chart.py       # ChartConfig for JSON chart export
    util/            # package_data, string utils
```

### Data Layout
```
data/
  kalshi/
    markets/    *.parquet   — market metadata (ticker, event_ticker, status, prices, result, etc.)
    trades/     *.parquet   — trade executions (trade_id, ticker, count, yes_price, taker_side, created_time)
  polymarket/
    markets/    *.parquet   — market metadata (id, condition_id, question, outcomes, prices, volume)
    trades/     *.parquet   — OrderFilled events from Polygon (maker, taker, amounts, block_number)
    blocks/     *.parquet   — block_number → timestamp lookup
    fpmm/       *.parquet   — legacy FPMM trades (pre-2022)
    fpmm_collateral_lookup.json
output/         — generated figures (PNG, PDF) and data (CSV, JSON)
```

### Key Data Schema Notes
**Kalshi:**
- Prices in **cents** (integer 1–99); `no_price = 100 - yes_price`
- `taker_side` = `'yes'` or `'no'`
- `status` = `'open'`, `'closed'`, `'finalized'`; `result` = `'yes'`, `'no'`, or `''`
- `ticker` links trades → markets; `event_ticker` groups related markets

**Polymarket:**
- Prices in **decimals** (float 0–1); `no_price = 1 - yes_price`
- Trades are raw blockchain events (`maker_amount`, `taker_amount` with 6 decimals for USDC)
- No direct `result` field — resolution must be inferred from `closed=True` + final `outcome_prices`
- Block → timestamp join needed for time-based analysis

### Analysis Framework
- Subclass `Analysis`, set `name` and `description`, implement `run() -> AnalysisOutput`
- Place files in `src/analysis/{kalshi,polymarket,comparison}/`
- `AnalysisOutput(figure=..., data=pd.DataFrame, chart=ChartConfig)`
- Run via `make analyze` (interactive menu) or `uv run main.py analyze <name>`
- Use `duckdb` for SQL queries on Parquet; `pandas` for DataFrames; `matplotlib` for plots

---

## 3. Active Development Goal: Relative Value Edge Structure

### Core Concept
Find prediction markets on **Kalshi** and **Polymarket** that cover **the same real-world event** but quote **different implied probabilities**, and measure the size, persistence, and tradability of that spread.

### Key Questions to Answer
1. **Market matching:** How do we reliably match Kalshi ↔ Polymarket markets on the same event? (text similarity, event category, resolution date alignment)
2. **Price normalization:** Kalshi cents vs. Polymarket decimals — need consistent probability space
3. **Edge definition:** What constitutes a meaningful RV edge? (raw spread, bid/ask adjusted spread, EV per contract)
4. **Edge persistence:** How long do mispricings persist before converging?
5. **Edge magnitude distribution:** By category (politics, sports, crypto, economics)
6. **Execution feasibility:** Liquidity, position limits, settlement timing differences

### Planned Deliverables (to be refined as prior chat is shared)
- [ ] Market matching / pairing module (`src/analysis/comparison/market_matcher.py`)
- [ ] Cross-platform price normalizer
- [ ] RV spread analysis (`src/analysis/comparison/relative_value_spread.py`)
- [ ] Edge persistence / half-life analysis
- [ ] Category-broken-down RV summary

---

## 4. Development Rules & Patterns

### Git
- **Always develop on:** `claude/prediction-market-relative-value-FXsMY`
- **Push with:** `git push -u origin claude/prediction-market-relative-value-FXsMY`
- Never push to `main` or `master`
- Retry push up to 4× on network failure (2s, 4s, 8s, 16s backoff)

### Code Style
- Python 3.9+, managed with `uv` (`uv sync` to install deps, `uv run` to execute)
- Type hints throughout; `from __future__ import annotations` at top
- `duckdb` for Parquet SQL (preferred over loading entire files into memory)
- Analyses placed in `src/analysis/` subfolders — they are auto-discovered by `Analysis.load()`

### Running Things
```bash
uv sync                          # install deps
make analyze                     # interactive analysis menu
uv run main.py analyze <name>    # run specific analysis
make index                       # interactive indexer menu
make setup                       # download + extract 36GiB dataset
```

### Testing
```bash
uv run pytest tests/             # run all tests
```
Tests cover: compile checks, analysis instantiation, analysis save pipeline.

---

## 5. Mistakes to Avoid (Updated as Discovered)

> Add entries here whenever a mistake is made so it is never repeated.

| # | Mistake | Correct Approach |
|---|---------|-----------------|
| 1 | _(none yet — will be populated as work begins)_ | — |

---

## 6. Key Context From Prior Conversations

> This section will be populated once prior chat history is shared.
> Each bullet should capture a concrete decision, constraint, or insight.

- _(awaiting prior chat paste)_

---

## 7. Open Questions / Clarifications Needed

> Items that need owner decision before implementation proceeds.

1. **Market matching strategy:** Manual curated mapping vs. automated NLP similarity vs. hybrid?
2. **Historical vs. live:** Is the RV analysis backward-looking (backtesting on historical data) or should it eventually be real-time?
3. **Execution scope:** Is this purely analytical/research, or will it eventually drive actual trades?
4. **Edge threshold:** What minimum spread (in probability points) is considered actionable?
5. **Priority order:** Which deliverable is highest priority — matching, spread analysis, or persistence?

---

## 8. Dependencies & Environment

| Package | Purpose |
|---------|---------|
| `duckdb` | SQL queries on Parquet files |
| `pandas` | DataFrames |
| `matplotlib` | Plotting |
| `scipy` | Statistical functions |
| `tqdm` | Progress indicators |
| `simple_term_menu` | Interactive CLI menus |
| `brokenaxes` | Broken-axis plots |
| `squarify` | Treemap visualizations |

Python version pinned in `.python-version`.
Full lock in `uv.lock`.

---

*Last updated: 2026-02-21 — Initial scaffold. Pending prior chat context.*
