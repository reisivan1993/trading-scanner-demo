# Cold Trader Scanner

End-of-day stock screening system that scans the S&P 500 universe for swing-trade setups (long and short). Runs after market close, applies technical and risk filters, enriches with web intelligence, and outputs actionable trade ideas.

## How the Scanner Works

The scanner runs an 11-stage pipeline from raw market data to ranked trade setups:

1. **Universe Loading** -- Reads the ticker list from `data/universe/spy.txt` (S&P 500 constituents). Configurable via `config.yml` (`max_tickers_per_run`).

2. **Pre-Filtering** -- Policy-driven filters eliminate tickers before expensive data fetching. Checks minimum price, minimum 20-day average dollar volume, and gap percentage thresholds. Rules live in `policies/default.yml`.

3. **Data Fetching** -- Pulls daily bars (250 trading days) and intraday bars (390 x 1-minute bars, one full session) from Polygon.io via the provider abstraction layer.

4. **Resampling** -- Converts raw bars into analysis timeframes:
   - 1m → 15m (intraday swing)
   - 1m → 65m (6 bars per session, institutional timeframe)
   - 1d → 1w (weekly context)

5. **Indicators** -- Computes technical indicators on daily and 65m frames:
   - ATR(14), EMA(9/20/50/200), SMA(200)
   - RSI(14), VWAP, RVOL (relative volume vs 20-day average)

6. **Pattern Detection** -- Identifies chart structures:
   - Support/resistance zones via price clustering
   - Vector candles (follow-through, absorption, rejection)
   - Breakouts, bull/bear flags, wedges, head & shoulders

7. **Setup Generation** -- For each ticker with detected patterns, calculates:
   - Entry price, stop loss (ATR-based, adjusted to S/R zones)
   - Target 1 and Target 2 (risk-multiple and S/R-based)
   - Position size (shares) from configured dollar risk
   - Risk-reward ratio

8. **Risk Gate** -- Rejects setups that fail any risk check:
   - Minimum R:R ratio (default 2.0)
   - Maximum stop distance as % of price
   - Minimum dollar volume (liquidity filter)
   - Penny stock filter (configurable)
   - Short-specific: minimum RVOL threshold

9. **Scoring** -- 7-factor weighted composite score (0-100):
   - Confluence (S/R + pattern alignment)
   - Invalidation clarity (clean stop level)
   - Risk-reward quality
   - Momentum (RSI, EMA alignment)
   - Volume confirmation (RVOL)
   - Pattern strength
   - Chart cleanliness

10. **Web Intelligence** -- Optional enrichment via Quercle API. Adds a sentiment modifier (+/-) to the composite score based on recent news and social signals.

11. **Ranking & Output** -- Sorts setups by composite score descending, assigns ranks 1-N. Generates markdown reports (English/Hebrew), TradingView watchlist exports, and optional Telegram notifications.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for UI)
- Docker & Docker Compose (optional)

### Setup

```bash
# Clone and enter project
cd trading-scanner-demo

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Unix

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Run the Scanner (CLI)

```bash
python -m packages.core.runner
```

### Run the API Server

```bash
uvicorn apps.api.main:app --reload
```

API endpoints:
- `POST /scan/run` - Trigger a full universe scan
- `POST /scan/ticker/{symbol}` - Scan a single ticker on demand
- `GET /scan/latest` - Get most recent results
- `GET /scan/{run_id}` - Get specific run results
- `GET /export/tradingview` - Export as TradingView watchlist
- `GET /health` - Health check

### Run the UI

```bash
cd apps/ui
npm install
npm run dev
```

### Docker

```bash
cd infra
docker compose up --build
```

- API: http://localhost:8000
- UI: http://localhost:3000

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=packages --cov-report=term-missing

# Unit tests only
pytest tests/unit/ -x

# Integration tests only
pytest tests/integration/ -v
```

## Architecture

```
packages/
  core/           # Config, models, resampling, indicators, orchestrator
  policy/         # Rule engine (schema, loader, engine with 8 hooks)
  providers/      # Market data (CSV, Polygon, Alpaca stub)
  skills/         # S/R zones, vector candles, patterns, risk gate, scoring
  tools/          # Web intelligence (Quercle)
apps/
  api/            # FastAPI + APScheduler
  ui/             # React + TypeScript dashboard
infra/            # Docker, nginx
policies/         # YAML policy files (default + user overrides + advanced)
data/
  universe/       # Ticker lists
  sample/         # Sample CSV data for testing
```

## Configuration

- `config.yml` - Main application config
- `policies/default.yml` - Default policy rules
- `policies/user_overrides.yml` - User customizations
- `policies/user_overrides_advanced.yml` - Advanced filters (risk gate extensions, short rules, etc.)
- `.env` - API keys (never committed)

## Key Features

- Multi-timeframe analysis (1m, 15m, 65m, daily, weekly)
- Support/resistance zone detection with clustering
- Vector candle identification (follow-through, absorption, rejection)
- Pattern detection (breakouts, flags, wedges, head & shoulders)
- Risk gating with configurable R:R, stop validation, dollar volume filters
- Weighted scoring across 7 dimensions + web intelligence modifier
- YAML-driven policy engine with deep merge layering
- Hebrew/English bilingual reporting
- TradingView watchlist export
- Telegram notifications (optional)
- Scheduled execution on US trading days
