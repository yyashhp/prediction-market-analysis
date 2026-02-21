# System Design — Prediction Market RV Dashboard

## 1. Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                      Dashboard UI                          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐            │
│  │Weathr│ │Sports│ │Macro │ │Crypto│ │ Poli │  (per-topic │
│  │Panel │ │Panel │ │Panel │ │Panel │ │Panel │   tabs)     │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘            │
│     └────────┴────────┴────────┴────────┘                 │
│                        │                                   │
│              ┌─────────▼──────────┐                        │
│              │   Edge Ranker /    │                        │
│              │   Kelly Sizer      │                        │
│              └─────────┬──────────┘                        │
└────────────────────────┼───────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐ ┌───────▼──────┐ ┌───────▼──────┐
│  Cross-Venue │ │ Term Struct  │ │  Threshold   │
│  Arb Detector│ │  Analyzer    │ │  CDF Fitter  │
└───────┬──────┘ └───────┬──────┘ └───────┬──────┘
        └────────────────┼────────────────┘
                         │
              ┌──────────▼──────────┐
              │   Market Matcher    │
              │  + Series Detector  │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  Topic Classifier   │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │   Price Normalizer  │
              └──────────┬──────────┘
                         │
           ┌─────────────┼─────────────┐
           │                           │
    ┌──────▼──────┐             ┌──────▼──────┐
    │ Kalshi Feed │             │ Polymarket  │
    │  (API poll) │             │ Feed (API)  │
    └─────────────┘             └─────────────┘
```

Data flows bottom-up: feeds → normalize → classify → match/group → detect edges → size → display.

---

## 2. Module Breakdown

### 2.1 `src/rv/` — Relative Value Core

All pure logic, no I/O. Independently testable with synthetic data.

#### `src/rv/normalizer.py` — Price Normalization

```python
@dataclass
class NormalizedQuote:
    """Unified quote in probability space (0-1)."""
    prob_mid: float          # midpoint probability
    prob_bid: float | None   # best bid (probability)
    prob_ask: float | None   # best ask (probability)
    spread: float | None     # ask - bid in probability points
    venue: str               # "kalshi" or "polymarket"
    raw_data: dict           # original API response for traceability

def from_kalshi(market: dict) -> NormalizedQuote:
    """Convert Kalshi cents (1-99) to probability (0.01-0.99)."""

def from_polymarket(market: dict) -> NormalizedQuote:
    """Convert Polymarket decimal (0-1) to probability."""
```

**Key concern:** Kalshi provides `yes_bid`, `yes_ask` as integer cents. Polymarket provides
`outcome_prices` as decimal strings. Both must map to the same probability scale.

#### `src/rv/classifier.py` — Topic Classification

```python
class Topic(Enum):
    WEATHER = "weather"
    SPORTS = "sports"
    MACRO = "macro"
    CRYPTO = "crypto"
    POLITICS = "politics"
    OTHER = "other"

def classify_kalshi(event_ticker: str, ticker: str, title: str) -> Topic:
    """Classify a Kalshi market using event_ticker prefix taxonomy."""
    # Uses existing src/analysis/kalshi/util/categories.py get_group() mapping

def classify_polymarket(question: str, slug: str) -> Topic:
    """Classify a Polymarket market using keyword matching + curated slugs."""
```

**Leverages:** The existing `src/analysis/kalshi/util/categories.py` which maps event_ticker
prefixes → groups like "Sports", "Economics", "Weather", etc.

#### `src/rv/matcher.py` — Market Matching & Series Detection

```python
@dataclass
class MarketPair:
    """A cross-venue pair: same event on Kalshi and Polymarket."""
    kalshi_market: dict
    polymarket_market: dict
    match_confidence: str  # "high", "medium", "low"
    match_method: str      # "curated", "fuzzy"

@dataclass
class ContractSeries:
    """A group of contracts forming a term structure or threshold series."""
    topic: Topic
    series_type: str          # "term_structure" or "threshold"
    contracts: list[dict]     # ordered by date or threshold
    venue: str                # "kalshi", "polymarket", or "cross"
    event_group: str          # e.g., "FOMC-2026", "CPI-JAN-2026"

def match_cross_venue(
    kalshi_markets: list[dict],
    polymarket_markets: list[dict],
    curated_pairs: dict | None = None,
) -> list[MarketPair]:
    """Match markets across venues."""

def detect_series(
    markets: list[dict],
    topic: Topic,
) -> list[ContractSeries]:
    """Detect term structure and threshold series within a topic."""
```

**Matching strategy (hybrid):**
1. Check curated pairs file first (high confidence)
2. For remaining: match by (a) same topic, (b) resolution date within ±1 day,
   (c) title similarity score > 0.85 (using difflib.SequenceMatcher — no ML deps)
3. Never auto-match non-standard/weird contracts

**Series detection strategy:**
- Kalshi: group by `event_ticker` — markets under same event ticker are a natural series
- Sort by `close_time` (term structure) or extract threshold from title via regex (threshold series)

#### `src/rv/edge.py` — Edge Calculation

```python
@dataclass
class Edge:
    """A detected mispricing opportunity."""
    edge_type: str            # "cross_venue", "term_structure", "threshold_cdf", "model_vs_market"
    topic: Topic
    magnitude_pp: float       # edge in probability points (e.g., 5.0 = 5pp)
    spread_ratio: float       # magnitude / average_spread (how many spreads is the edge?)
    direction: str            # "buy_kalshi_sell_poly", "buy_contract_X", etc.
    contracts: list[dict]     # the contract(s) involved
    liquidity_grade: str      # "A", "B", "C"
    kelly_fraction: float     # suggested bankroll fraction
    kelly_size_usd: float     # dollar amount at given bankroll

def compute_cross_venue_edge(pair: MarketPair) -> Edge | None:
    """Edge = abs(kalshi_mid - poly_mid) adjusted for spreads on both sides."""

def compute_term_structure_edges(series: ContractSeries) -> list[Edge]:
    """Find monotonicity violations in a term structure series."""

def compute_threshold_edges(series: ContractSeries) -> list[Edge]:
    """Fit parametric distribution to implied CDF; find residual contracts."""

def compute_model_edge(
    market: dict,
    model_probability: float,
    quote: NormalizedQuote,
) -> Edge | None:
    """Edge = model_prob - market_mid, filtered by spread."""
```

**Threshold CDF fitting approach:**
1. Extract threshold values from contract titles (regex)
2. Map each threshold → implied probability (from market mid price)
3. These points define an empirical CDF of the underlying variable
4. Fit `scipy.stats.norm` (or lognorm) via least-squares to get implied μ, σ
5. Residual = market_prob - fitted_prob for each contract
6. Contracts with |residual| > threshold are edge candidates

#### `src/rv/kelly.py` — Kelly Criterion Sizing

```python
def kelly_fraction(
    edge: float,           # probability edge (e.g., 0.05 for 5pp)
    win_prob: float,       # estimated true probability of winning
    odds: float,           # payout odds (for binary: (1/price) - 1)
    fraction: float = 0.5, # fractional Kelly (default: half-Kelly)
) -> float:
    """Compute fractional Kelly bet size as fraction of bankroll."""
    # f* = (p * (b+1) - 1) / b   where p = win_prob, b = odds
    # Apply fraction multiplier for safety

def size_position(
    edge: Edge,
    bankroll: float,
    max_per_contract: float,
    max_per_topic: float,
    max_per_venue: float,
    max_total: float,
    current_exposure: dict,  # track existing positions
) -> float:
    """Compute dollar position size with all caps applied."""
```

#### `src/rv/liquidity.py` — Liquidity Assessment

```python
@dataclass
class LiquidityFilter:
    min_volume_24h: float = 500.0   # minimum $500 daily volume
    max_spread: float = 0.10        # maximum 10% (10 cent) spread
    min_open_interest: int = 200    # minimum 200 contracts OI

def grade_liquidity(quote: NormalizedQuote, volume_24h: float, oi: int) -> str:
    """Return 'A', 'B', or 'C' liquidity grade."""

def passes_filter(
    quote: NormalizedQuote,
    volume_24h: float,
    oi: int,
    filters: LiquidityFilter,
) -> bool:
    """Check if a contract meets minimum liquidity thresholds."""
```

### 2.2 `src/live/` — Live Data Feeds

Handles all API I/O. Produces normalized market snapshots consumed by `src/rv/`.

#### `src/live/kalshi_feed.py`

```python
class KalshiFeed:
    """Polls Kalshi API for active markets and quotes."""

    def __init__(self, api_key: str | None = None):
        # Uses kalshi-python SDK (already in deps)

    def fetch_active_markets(self) -> list[dict]:
        """Fetch all active markets with current quotes."""

    def fetch_markets_by_event(self, event_ticker: str) -> list[dict]:
        """Fetch all markets under a specific event."""
```

#### `src/live/polymarket_feed.py`

```python
class PolymarketFeed:
    """Polls Polymarket CLOB API for active markets."""

    def __init__(self):
        # Uses polymarket-py SDK or direct httpx to gamma API

    def fetch_active_markets(self) -> list[dict]:
        """Fetch all active markets with current prices."""
```

#### `src/live/reference_feeds.py`

```python
class NWSWeatherFeed:
    """Fetch NWS probability forecasts for weather markets."""

class CMEFedWatchFeed:
    """Fetch CME FedWatch implied probabilities for rate decisions."""

class VegasOddsFeed:
    """Fetch consensus sports odds from public API."""
```

#### `src/live/feed_manager.py`

```python
class FeedManager:
    """Orchestrates all feeds on configurable polling intervals."""

    def __init__(self, config: dict):
        self.kalshi = KalshiFeed(...)
        self.polymarket = PolymarketFeed(...)
        self.references = {...}
        self.poll_interval = config.get("poll_interval", 60)

    def snapshot(self) -> MarketSnapshot:
        """Fetch all sources and return a unified snapshot."""
        # Normalize all prices, classify topics, return structured data
```

### 2.3 `src/dashboard/` — Dashboard UI

#### Technology Decision (Pending — See Open Questions)

**Option A: Streamlit** (current lean)
- `streamlit run src/dashboard/app.py`
- `st.rerun()` for auto-refresh; `st.tabs()` for topic panels
- Renders matplotlib natively; minimal boilerplate
- New dependency: `streamlit`

**Option B: Textual** (terminal)
- No browser needed; runs in terminal
- Rich tables, live updating
- New dependency: `textual`

**Option C: Rich tables** (simplest terminal)
- Just a `while True` loop printing `rich.table.Table` every N seconds
- No new framework dependency beyond `rich`
- Good enough for v1?

#### `src/dashboard/app.py`

```python
# Entry point for the dashboard, regardless of UI choice

def main():
    config = load_config()
    feed_manager = FeedManager(config)

    while True:
        snapshot = feed_manager.snapshot()
        edges = compute_all_edges(snapshot)
        filtered = apply_liquidity_filters(edges, config)
        sized = apply_kelly_sizing(filtered, config)
        render(sized)  # UI-specific rendering
        sleep(config["poll_interval"])
```

---

## 3. Configuration

All configuration via `config/dashboard.yaml` (or `.json`), with `.env` for secrets.

```yaml
# config/dashboard.yaml
polling:
  market_interval: 60        # seconds between market data refreshes
  reference_interval: 300    # seconds between reference model refreshes

topics:
  enabled: [weather, sports, macro]
  disabled: [crypto, politics]

liquidity:
  min_volume_24h: 500
  max_spread: 0.10
  min_open_interest: 200

edge:
  min_magnitude_pp: 3.0      # minimum edge in probability points to display

kelly:
  bankroll: 10000             # total bankroll in USD
  fraction: 0.5              # half-Kelly
  max_per_contract: 500
  max_per_topic: 2000
  max_per_venue: 3000
  max_total: 5000

api_keys:
  kalshi: "${KALSHI_API_KEY}"         # from .env
  kalshi_email: "${KALSHI_EMAIL}"     # from .env
```

---

## 4. Data Flow (One Refresh Cycle)

```
1. FeedManager.snapshot()
   ├── KalshiFeed.fetch_active_markets()        → list[dict]
   ├── PolymarketFeed.fetch_active_markets()     → list[dict]
   └── ReferenceFeed.fetch() (if stale)          → dict[topic, model_probs]

2. Normalize
   ├── from_kalshi(market) → NormalizedQuote      (for each Kalshi market)
   └── from_polymarket(market) → NormalizedQuote   (for each Poly market)

3. Classify
   ├── classify_kalshi(event_ticker, ticker, title) → Topic
   └── classify_polymarket(question, slug) → Topic

4. Filter by liquidity
   └── passes_filter(quote, volume, oi, thresholds) → bool

5. Group & Match
   ├── match_cross_venue(kalshi, poly, curated) → list[MarketPair]
   └── detect_series(markets, topic) → list[ContractSeries]

6. Compute Edges
   ├── compute_cross_venue_edge(pair) → Edge | None
   ├── compute_term_structure_edges(series) → list[Edge]
   ├── compute_threshold_edges(series) → list[Edge]
   └── compute_model_edge(market, ref_prob, quote) → Edge | None

7. Size & Rank
   ├── kelly_fraction(edge, win_prob, odds) → float
   ├── size_position(edge, bankroll, caps, exposure) → float
   └── sort by spread_ratio descending

8. Render per-topic panels in dashboard
```

---

## 5. File Structure (New Files)

```
src/
  rv/
    __init__.py
    normalizer.py         # NormalizedQuote, from_kalshi(), from_polymarket()
    classifier.py         # Topic enum, classify_kalshi(), classify_polymarket()
    matcher.py            # MarketPair, ContractSeries, match_cross_venue(), detect_series()
    edge.py               # Edge dataclass, compute_*_edge() functions
    kelly.py              # kelly_fraction(), size_position()
    liquidity.py          # LiquidityFilter, grade_liquidity(), passes_filter()

  live/
    __init__.py
    kalshi_feed.py        # KalshiFeed class
    polymarket_feed.py    # PolymarketFeed class
    reference_feeds.py    # NWSWeatherFeed, CMEFedWatchFeed, VegasOddsFeed
    feed_manager.py       # FeedManager orchestrator

  dashboard/
    __init__.py
    app.py                # Main entry point
    config.py             # Config loading (YAML + .env)
    renderer.py           # UI rendering (Streamlit / Textual / Rich — TBD)

config/
  dashboard.yaml          # Default configuration
  matched_pairs.json      # Curated cross-venue market pairs
  topic_overrides.json    # Manual topic reclassification overrides

tests/
  test_normalizer.py
  test_classifier.py
  test_matcher.py
  test_edge.py
  test_kelly.py
  test_liquidity.py
  test_feeds.py           # Mocked API responses
```

---

## 6. Implementation Phases

### Phase 1: RV Core (`src/rv/`) — No I/O, Pure Logic
Build and test all computation modules with synthetic data.
1. `normalizer.py` + tests
2. `classifier.py` + tests (integrate existing `categories.py`)
3. `liquidity.py` + tests
4. `kelly.py` + tests
5. `edge.py` + tests (cross-venue, term structure, threshold CDF)
6. `matcher.py` + tests

### Phase 2: Live Feeds (`src/live/`) — API Integration
Wire up real API polling.
1. `kalshi_feed.py` + tests (mock responses)
2. `polymarket_feed.py` + tests (mock responses)
3. `feed_manager.py` + snapshot integration test
4. Config loading (`dashboard.yaml` + `.env`)

### Phase 3: Dashboard (`src/dashboard/`) — UI
Build the display layer.
1. Choose UI technology (Streamlit / Textual / Rich)
2. `app.py` main loop
3. Per-topic panel rendering
4. Edge table with color coding
5. Auto-refresh loop

### Phase 4: Reference Models (`src/live/reference_feeds.py`) — External Alpha
Add external model integrations.
1. NWS Weather API integration
2. CME FedWatch scraper/API
3. Vegas odds API integration
4. Model-vs-market edge computation

### Phase 5: Polish & Backtest Mode (Optional)
1. Historical backtest mode using stored Parquet data
2. Edge persistence / half-life analysis
3. P&L tracking (paper trading log)

---

## 7. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Price normalization target | 0-1 float probability | More natural for statistical operations; convert to cents only for display |
| Market matching | Hybrid curated + fuzzy | Curated for reliability on high-priority pairs; fuzzy for discovery |
| CDF fitting | `scipy.stats.norm.fit` | Simple, well-understood; log-normal available for skewed distributions |
| Fuzzy text matching | `difflib.SequenceMatcher` | Already in stdlib; no ML dependency; sufficient for structured contract titles |
| Configuration format | YAML + .env | YAML for readable config; .env for secrets (already have `python-dotenv` in deps) |
| Polling approach | Synchronous loop with `time.sleep` | Prediction markets don't need sub-second latency; simplicity > async complexity |

---

## 8. Risk & Mitigations

| Risk | Mitigation |
|------|-----------|
| Kalshi API rate limiting | Respect rate limits; exponential backoff via `tenacity`; cache metadata |
| Polymarket API instability | Graceful degradation; show Kalshi-only data if Poly is down |
| False market matches | Curated pairs for high-priority; confidence scores; manual override file |
| Stale data leading to bad edges | Timestamp every quote; display staleness warning if > 2× poll interval |
| Kelly over-sizing | Half-Kelly default; hard caps at every level; conservative edge estimates |
| CDF fitting to sparse data | Require minimum 3 contracts in a threshold series to attempt fit |
| Wide spreads eating edge | Express all edges in spread units; don't surface < 1 spread edges |
