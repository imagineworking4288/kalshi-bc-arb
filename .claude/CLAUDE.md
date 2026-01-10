# CLAUDE.md - Kalshi Arbitrage Trading Platform

> **Quick Reference for AI Assistants**
> This document provides comprehensive context for working on the Kalshi prediction market arbitrage trading platform.

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [⚠️ Critical Constraints](#critical-constraints)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Trading Strategies](#trading-strategies)
- [Data Models](#data-models)
- [Code Patterns](#code-patterns)
- [File Structure](#file-structure)
- [Environment Variables](#environment-variables)
- [Quick Commands](#quick-commands)
- [Testing Strategy](#testing-strategy)

---

## Project Overview

**Purpose**: Automated prediction market arbitrage detection and execution on Kalshi with paper trading simulation.

### Tech Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Backend | FastAPI | 0.109.0 | REST API server |
| Frontend | React + TypeScript | 18.x | Web UI |
| State Management | Zustand | 4.x | Client state |
| Styling | Tailwind CSS | 3.x | UI styling |
| Database | SQLite + aiosqlite | 0.19.0 | Local storage |
| Auth | cryptography (RSA-PSS) | 42.0.0 | Kalshi API auth |
| HTTP Client | httpx | 0.26.0 | Async HTTP |
| Build Tool | Vite | 5.x | Frontend bundler |
| WebSocket | FastAPI WebSocket | - | Real-time updates |

### Key Features

- **Dual Trading Modes**: Paper simulation (default) + Live trading
- **Multiple Arbitrage Strategies**: BTC threshold/range, Weather brackets, Economic events
- **Portfolio Management**: Position tracking, P&L analytics, order history
- **Risk Management**: Kelly sizing, circuit breakers, position limits
- **Real-time Scanning**: BTC (2s), Weather (30s) independent scanners
- **Unified Trading Infrastructure**: Strategy orchestrator with signal management

---

## ⚠️ Critical Constraints

### 🚫 Position Limitation (MOST IMPORTANT)

**Kalshi does NOT allow holding YES and NO on the same market simultaneously.**

This constraint shapes ALL strategy code:

```python
# ❌ INVALID - Cannot do this
buy_yes("KXBTC-24DEC31-100000")
buy_no("KXBTC-24DEC31-100000")  # Will fail!

# ✅ VALID - Bracket arbitrage works
buy_yes("KXBTC-24DEC31-100000-100499")  # Range market
buy_no("KXBTC-24DEC31-100000")  # Threshold market (different ticker)
```

**Why this matters:**
- Prevents simple "hedge both sides" strategies
- Requires finding correlated markets with different tickers
- Bracket arbitrage works because each bracket is a separate market
- Must check existing positions before placing opposing trades

### Rate Limits by Tier

| Tier | Rate Limit | Notes |
|------|------------|-------|
| Free | 10 req/sec | Sufficient for scanning |
| Standard | 30 req/sec | Recommended for live trading |
| Premium | 100 req/sec | High-frequency strategies |

**Implementation**: Exponential backoff on 429 errors (see `kalshi_client.py:70-78`)

### Port Configuration

| Service | Port | Notes |
|---------|------|-------|
| Backend | 8001 | FastAPI server |
| Frontend (dev) | 5173 | Vite dev server |
| Frontend (prod) | 80/443 | Static hosting |

---

## Architecture

### 4-Terminal Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Terminal 1    │    │   Terminal 2    │    │   Terminal 3    │
│   Frontend      │◄──►│   Backend API   │◄──►│   Scanners      │
│   React/Vite    │    │   FastAPI       │    │   BTC/Weather   │
│   :5173         │    │   :8001         │    │   SQLite Write  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                             │                        │
                             │                        ▼
                             │                 ┌─────────────────┐
                             │                 │ scanner_results │
                             └────────────────►│    .db          │
                                   (reads)     │                 │
                                               └─────────────────┘
                                                        │
                        ┌───────────────────────────────┘
                        ▼
                 ┌─────────────────┐
                 │   Terminal 4    │
                 │   Log Viewer    │
                 │   Colored logs  │
                 └─────────────────┘
```

**Key Insight**: Scanners write to SQLite independently, API reads instantly (no blocking).

### Data Flow

1. **Scanners** (Terminal 3) continuously scan Kalshi API
2. **Write** results to `scanner_results.db`
3. **Backend** (Terminal 2) reads from database instantly
4. **Frontend** (Terminal 1) polls backend every 30s
5. **Logs** (Terminal 4) aggregate all service output

---

## API Reference

### Base URLs

```
Production (ALL markets): https://api.elections.kalshi.com/trade-api/v2
WebSocket:                wss://api.elections.kalshi.com/trade-api/ws/v2
```

⚠️ **Important**: Use `api.elections.kalshi.com` for ALL markets (not just elections). This is the unified endpoint.

### Authentication

**Method**: RSA-PSS signature with SHA-256

**Headers Required**:
```http
KALSHI-ACCESS-KEY: <api_key_id>
KALSHI-ACCESS-TIMESTAMP: <unix_timestamp_ms>
KALSHI-ACCESS-SIGNATURE: <base64_signature>
Content-Type: application/json
```

**Signature Process**:

```python
# 1. Create message
timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
path_without_query = "/trade-api/v2/markets"  # Strip ?params
message = f"{timestamp}GET{path_without_query}"

# 2. Sign with RSA-PSS
signature = private_key.sign(
    message.encode(),
    padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH  # ⚠️ DIGEST_LENGTH not MAX_LENGTH
    ),
    hashes.SHA256()
)

# 3. Base64 encode
signature_b64 = base64.b64encode(signature).decode()
```

**Common Auth Pitfalls**:

❌ Using `PSS.MAX_LENGTH` → Use `PSS.DIGEST_LENGTH`
❌ Including query params in signature → Strip them first
❌ Wrong timestamp format → Must be milliseconds, not seconds
❌ Lowercase method → Must be uppercase (GET not get)

### Key Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/markets` | GET | Required | List markets with filters |
| `/markets/{ticker}` | GET | Required | Single market details |
| `/markets/{ticker}/orderbook` | GET | Required | Order book depth |
| `/events` | GET | Required | Events with nested markets |
| `/portfolio/balance` | GET | Required | Account balance |
| `/portfolio/positions` | GET | Required | Current positions |
| `/portfolio/orders` | POST | Required | Place single order |
| `/portfolio/orders/batched` | POST | Required | Atomic multi-leg execution |
| `/portfolio/fills` | GET | Required | Fill history |

**Rate Limit Headers**:
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1234567890
```

---

## Trading Strategies

### 1. Bracket Arbitrage (Mutually Exclusive Markets)

**Concept**: Buy all outcomes in a mutually exclusive set when total cost < guaranteed payout.

**Three Strategies**:

#### All YES
Buy YES on every bracket. Arbitrage if `sum(yes_ask) < 100¢`.

```python
# Example: Temperature brackets (mutually exclusive)
brackets = [
    {"ticker": "KXHIGHNY-24DEC31-60-61", "yes_ask": 25},  # 25¢
    {"ticker": "KXHIGHNY-24DEC31-61-62", "yes_ask": 30},  # 30¢
    {"ticker": "KXHIGHNY-24DEC31-62-63", "yes_ask": 20},  # 20¢
]
total_cost = 75¢
payout = 100¢ (exactly ONE will be YES)
profit = 25¢ (before fees)
```

#### All NO
Buy NO on every bracket. Arbitrage if `sum(no_ask) < (n-1) × 100¢`.

```python
# n=4 brackets, so (n-1) = 3 will pay out
total_cost = 280¢
payout = 3 × 100¢ = 300¢
profit = 20¢
```

#### Min 2-NO
Buy 2 cheapest NOs. Arbitrage if `no1 + no2 < 100¢`.

```python
# Only works if exactly 1 outcome happens
cheapest_nos = [35¢, 40¢]
total_cost = 75¢
payout = 100¢ (both NOs pay if neither bracket hits)
profit = 25¢
```

**Fee Calculation**:

```python
# Kalshi fee: 7% × contracts × price × (1 - price)
# Rounded up to nearest cent

def calculate_fee(contracts: int, price_cents: int) -> int:
    price = price_cents / 100.0
    fee = 0.07 * contracts * price * (1 - price) * 100
    return max(1, int(fee + 0.99))  # Round up

# Example: 10 contracts at 60¢
fee = 0.07 × 10 × 0.60 × 0.40 × 100 = 16.8¢ → 17¢
```

### 2. Weather Market Arbitrage

**Coverage**: 7 cities × 2 types = 14 series

| City | High Series | Low Series |
|------|-------------|------------|
| New York | KXHIGHNY | KXLOWNY |
| Los Angeles | KXHIGHLA | KXLOWLA |
| Chicago | KXHIGHCH | KXLOWCH |
| Miami | KXHIGHMI | KXLOWMI |
| Denver | KXHIGHDE | KXLOWDE |
| Austin | KXHIGHAU | KXLOWAU |
| Philadelphia | KXHIGHPH | KXLOWPH |

**NWS Integration**: National Weather Service API provides 7-day forecasts with location-specific adjustments:

```python
# Location adjustments
adjustments = {
    "NYC": {
        "urban_heat": +1.5,      # Urban heat island effect
        "coastal_damping": 0.95   # Atlantic moderating influence
    },
    "DEN": {
        "altitude": -3.0,         # Higher elevation = cooler
        "dry_amplification": 1.1  # Dry air = larger swings
    }
}
```

**Scan Frequency**: Every 30 seconds

### 3. BTC Threshold/Range Arbitrage

**Market Types**:
- **KXBTC**: Range markets (e.g., $87,500-$87,749.99)
- **KXBTCD**: Threshold markets (e.g., > $87,500)

**Arbitrage Pattern**:

```python
# Buy YES on range, NO on both thresholds
range_market = "KXBTC-24DEC31-87500-87749"   # YES at 40¢
lower_threshold = "KXBTCD-24DEC31-87500"     # NO at 25¢
upper_threshold = "KXBTCD-24DEC31-87750"     # YES at 30¢

total_cost = 40 + 25 + 30 = 95¢
payout = 100¢ (guaranteed)
profit = 5¢ before fees
```

**Scan Frequency**: Every 2 seconds

---

## Data Models

### Market Object (from Kalshi API)

```python
{
    "ticker": "KXHIGHNY-24DEC31-60-61",
    "title": "Will the high temperature in NYC be 60-61°F on Dec 31?",
    "subtitle": "be 60-61°",  # Parsed for bracket bounds
    "event_ticker": "KXHIGHNY-24DEC31",
    "market_type": "binary",
    "yes_ask": 35,  # Best YES ask price in cents
    "yes_bid": 30,  # Best YES bid price in cents
    "no_ask": 70,   # Best NO ask price in cents
    "no_bid": 65,   # Best NO bid price in cents
    "volume": 1250, # 24h volume
    "open_interest": 450,
    "settlement_time": "2024-12-31T23:59:00Z",
    "floor_strike": 60,   # For bracket markets
    "cap_strike": 61,     # For bracket markets
    "status": "open"
}
```

### Order Request

```python
# Single order
{
    "ticker": "KXHIGHNY-24DEC31-60-61",
    "client_order_id": "uuid-string",  # Optional
    "side": "yes",  # or "no"
    "action": "buy",  # or "sell"
    "count": 10,
    "type": "limit",
    "yes_price": 35,  # Price in cents (1-99)
    "expiration_ts": 1234567890000,  # Optional
    "sell_position_floor": 0  # For sells only
}

# Batch orders (atomic execution)
{
    "orders": [
        {"ticker": "...", "side": "yes", "action": "buy", ...},
        {"ticker": "...", "side": "no", "action": "buy", ...}
    ]
}
```

### Fee Calculation Formula

```python
# Base fee
fee = ceil(0.07 × contracts × price × (1 - price))

# Maker discount (50% off for limit orders that provide liquidity)
if is_maker:
    fee = ceil(fee × 0.5)

# Examples
calc_fee(10, 50) = ceil(0.07 × 10 × 0.50 × 0.50) = 2¢
calc_fee(10, 60) = ceil(0.07 × 10 × 0.60 × 0.40) = 2¢
calc_fee(100, 30) = ceil(0.07 × 100 × 0.30 × 0.70) = 15¢
```

---

## Code Patterns

### ✅ Correct Position Handling

```python
# Check existing positions before trading
async def can_trade(ticker: str, side: str) -> bool:
    positions = await kalshi_client.get_positions()
    existing = next((p for p in positions if p["ticker"] == ticker), None)

    if existing:
        # Can't buy opposite side
        if existing["side"] != side:
            return False

    return True

# Safe trade execution
if await can_trade(ticker, "yes"):
    await place_order(ticker, "yes", "buy", contracts, price)
else:
    logger.warning(f"Cannot trade {ticker}: opposite position exists")
```

### ❌ Incorrect Patterns (Will Fail)

```python
# Don't do this - will violate position constraint
await place_order("TICKER", "yes", "buy", 10, 50)
await place_order("TICKER", "no", "buy", 10, 50)  # ❌ ERROR

# Don't hedge same market
positions = [{"ticker": "TICKER", "side": "yes", "contracts": 10}]
await place_order("TICKER", "no", "buy", 10, 50)  # ❌ ERROR
```

### Safety-First Patterns

#### Circuit Breaker

```python
class CircuitBreaker:
    def __init__(self, max_consecutive_losses=5, cooldown_seconds=300):
        self.consecutive_losses = 0
        self.is_tripped = False
        self.trip_time = None

    def record_result(self, won: bool):
        if won:
            self.consecutive_losses = 0
            self.is_tripped = False
        else:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.trip()

    def can_trade(self) -> bool:
        if self.is_tripped:
            if time.time() - self.trip_time > self.cooldown_seconds:
                self.reset()
        return not self.is_tripped
```

#### Kelly Criterion Sizing

```python
def calculate_kelly_size(model_prob: float, market_price: float, bankroll: float) -> int:
    """
    Kelly Criterion: f = (p × odds - (1-p)) / odds

    Where:
    - p = model probability
    - odds = (1 / market_price) - 1
    """
    if model_prob <= market_price:
        return 0  # No edge

    edge = model_prob - market_price
    odds = (1 / market_price) - 1
    kelly_fraction = (model_prob * odds - (1 - model_prob)) / odds

    # Use 25% Kelly for safety (fractional Kelly)
    kelly_fraction *= 0.25

    # Calculate position size
    position_value = bankroll * kelly_fraction
    contracts = int(position_value / market_price)

    # Apply limits
    return min(contracts, 100)  # Max 100 contracts
```

#### Risk Manager

```python
class RiskManager:
    def check_trade(self, ticker: str, contracts: int, price: float) -> bool:
        # Position limits
        if contracts > self.max_position_per_market:
            return False

        # Total exposure
        total_positions = sum(p["contracts"] for p in self.positions.values())
        if total_positions + contracts > self.max_total_position:
            return False

        # Daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            return False

        # Single trade size
        trade_value = contracts * price
        if trade_value > self.max_single_trade:
            return False

        return True
```

---

## File Structure

```
kalshi-bc-arb/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config/
│   │   ├── __init__.py           # Settings (Pydantic)
│   │   ├── fees.py               # Fee calculations
│   │   └── locations/            # Weather location configs
│   ├── api/
│   │   ├── routes.py             # REST endpoints
│   │   └── websocket.py          # WebSocket manager
│   ├── database/
│   │   ├── connection.py         # SQLite async wrapper
│   │   └── schema.sql            # Database schema
│   ├── models/
│   │   └── schemas.py            # Pydantic models
│   ├── services/
│   │   ├── kalshi_client.py      # Kalshi API client
│   │   ├── spot_price_client.py  # BTC price (free APIs)
│   │   ├── arbitrage_calculator.py
│   │   ├── arbitrage_detector.py
│   │   ├── market_classifier.py
│   │   ├── fee_calculator.py
│   │   ├── paper_trading.py      # Simulation engine
│   │   ├── trade_executor.py     # Paper/live router
│   │   ├── portfolio_service.py
│   │   ├── watchlist_service.py
│   │   ├── edge_detector.py
│   │   ├── auto_trader.py
│   │   ├── btc_arb_scanner.py
│   │   ├── btc_arb_engine.py
│   │   ├── weather_arb_scanner.py
│   │   ├── scanner_service.py
│   │   ├── scanner_db.py
│   │   ├── nws_client.py         # Weather forecasts
│   │   ├── log_config.py
│   │   ├── log_viewer.py
│   │   └── core/                 # Unified trading infrastructure
│   │       ├── base_strategy.py
│   │       ├── signal_manager.py
│   │       ├── kelly_sizing.py
│   │       ├── risk_manager.py
│   │       ├── circuit_breaker.py
│   │       ├── batch_executor.py
│   │       ├── performance_tracker.py
│   │       ├── alert_service.py
│   │       ├── strategy_orchestrator.py
│   │       └── backtest_engine.py
│   └── utils/
│       ├── kalshi_auth.py        # RSA-PSS signing
│       └── logger.py
├── frontend/
│   ├── src/
│   │   ├── main.tsx              # React entry
│   │   ├── App.tsx               # Root component
│   │   ├── components/
│   │   │   ├── arbitrage/        # Arbitrage hub
│   │   │   ├── portfolio/
│   │   │   ├── trade/
│   │   │   ├── watchlist/
│   │   │   ├── autotrader/
│   │   │   ├── analytics/
│   │   │   ├── layout/
│   │   │   └── common/
│   │   ├── hooks/
│   │   │   └── useSpotPrice.ts
│   │   ├── services/
│   │   │   └── api.ts            # Backend client
│   │   ├── stores/
│   │   │   ├── opportunityStore.ts
│   │   │   └── tradingStore.ts
│   │   ├── types/
│   │   │   ├── index.ts
│   │   │   └── weather.ts
│   │   └── utils/
│   │       └── format.ts
│   ├── package.json
│   └── vite.config.ts
├── context/                       # AI assistant context
│   ├── INDEX.md                  # File tree and modules
│   ├── API.md                    # API reference
│   └── SCHEMAS.md                # Data schemas
├── run_scanners.py               # Scanner entry point
├── run_logs.py                   # Log viewer entry point
├── test_core_components.py       # Core tests
├── start.bat                     # Launch all services
├── stop.bat                      # Stop all services
├── .env                          # Environment config
├── README.md
├── ARCHITECTURE.md               # 4-terminal architecture
├── QUICKSTART.md
└── CLAUDE.md                     # This file
```

### Key Entry Points

| File | Command | Purpose |
|------|---------|---------|
| `backend/main.py` | `uvicorn backend.main:app --reload --port 8001` | Start API server |
| `frontend/src/main.tsx` | `npm run dev` (in frontend/) | Start React dev server |
| `run_scanners.py` | `python run_scanners.py` | Run BTC + Weather scanners |
| `run_logs.py` | `python run_logs.py` | Start log viewer |
| `start.bat` | `start.bat` | Launch all 4 terminals |
| `test_core_components.py` | `python test_core_components.py` | Test core infrastructure |

---

## Environment Variables

### Required for Live Trading

```bash
KALSHI_API_KEY_ID=your-key-id-here
KALSHI_PRIVATE_KEY_PATH=./keys/kalshi-private-key.pem
PAPER_TRADING_MODE=false  # WARNING: Real money!
```

### Optional Configuration

```bash
# API Base URL (default shown)
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
KALSHI_WS_URL=wss://api.elections.kalshi.com/trade-api/ws/v2

# Paper Trading (default: True)
PAPER_TRADING_MODE=true
PAPER_STARTING_BALANCE=10000.00
INITIAL_PAPER_BALANCE=1000000  # In cents

# Scanner Settings
BTC_SCAN_INTERVAL=2.0           # Seconds
WEATHER_SCAN_INTERVAL=30.0      # Seconds

# Database Paths
DATABASE_PATH=./data/kalshi.db
SCANNER_DB_PATH=./data/scanner_results.db

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### No Configuration Needed

- **BTC Spot Price**: Uses free APIs (CoinGecko, CoinLore)
- **Weather Forecasts**: NWS API is free and public
- **Frontend**: Automatically connects to localhost:8001

---

## Quick Commands

### First Time Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install

# Create .env
cp .env.example .env
# Edit .env with your Kalshi credentials
```

### Start Platform (4 Terminals)

```bash
# Option 1: All at once (Windows)
start.bat

# Option 2: Manual (cross-platform)
# Terminal 1
cd frontend && npm run dev

# Terminal 2
cd backend && uvicorn main:app --reload --port 8001

# Terminal 3
python run_scanners.py

# Terminal 4
python run_logs.py
```

### Stop Platform

```bash
# Option 1: Close launcher terminal
# Option 2: Manual
stop.bat

# Option 3: Kill processes
# Windows
taskkill /IM node.exe /F
taskkill /IM python.exe /F

# Linux/Mac
pkill -f "npm run dev"
pkill -f "uvicorn"
pkill -f "run_scanners"
pkill -f "run_logs"
```

### Development Commands

```bash
# Backend tests
python test_core_components.py

# Frontend dev
cd frontend
npm run dev          # Dev server
npm run build        # Production build
npm run preview      # Preview build

# Linting
cd frontend
npm run lint

# Check API
curl http://localhost:8001/health
curl http://localhost:8001/scanners/status

# View logs
python run_logs.py --source weather --level INFO
python run_logs.py --file errors
tail -f logs/kalshi.log
```

### Database Operations

```bash
# View scanner results
sqlite3 data/scanner_results.db
> SELECT * FROM scanner_results;
> SELECT * FROM scanner_stats;

# View trading data
sqlite3 data/kalshi.db
> SELECT * FROM paper_account;
> SELECT * FROM paper_positions WHERE settled = 0;
> SELECT * FROM paper_trades ORDER BY executed_at DESC LIMIT 10;
```

---

## Testing Strategy

### Testing Philosophy

**Safety First**: Test with paper trading before ANY live changes.

### Test Levels

#### 1. Unit Tests

```bash
# Test core components
python test_core_components.py

# Test specific modules
python -m pytest backend/services/test_*.py
```

**Key Tests**:
- Fee calculations (must match Kalshi exactly)
- Arbitrage detection (all three strategies)
- Position constraint validation
- Kelly sizing calculations
- Circuit breaker logic

#### 2. Integration Tests

```bash
# Start backend in test mode
PAPER_TRADING_MODE=true uvicorn backend.main:app

# Test endpoints
curl http://localhost:8001/opportunities?min_profit=1.0
curl http://localhost:8001/btc-arb/status
curl http://localhost:8001/weather-arb/status
```

#### 3. Scanner Tests

```bash
# Run scanners once
python run_scanners.py

# Check database
sqlite3 data/scanner_results.db "SELECT * FROM scanner_results"

# Verify calculations
python -c "from backend.services.btc_arb_scanner import BTCArbitrageScanner; \
           scanner = BTCArbitrageScanner(...); \
           result = await scanner.scan()"
```

#### 4. Paper Trading Tests

**Workflow**:

1. Enable paper mode: `PAPER_TRADING_MODE=true`
2. Reset paper account: `curl -X POST http://localhost:8001/paper/reset`
3. Execute trades via UI or API
4. Monitor positions: `curl http://localhost:8001/positions`
5. Check P&L: `curl http://localhost:8001/paper/summary`
6. Review logs: `tail -f logs/trades.log`

#### 5. Live Trading Tests (Use Caution!)

⚠️ **WARNING**: Real money! Test thoroughly in paper mode first.

```bash
# 1. Set conservative limits in .env
MAX_POSITION_PER_MARKET=10  # Small position
MAX_DAILY_LOSS_CENTS=1000   # $10 max loss
CIRCUIT_BREAKER_MAX_LOSSES=2  # Trip quickly

# 2. Enable live mode
PAPER_TRADING_MODE=false

# 3. Start with manual execution only
# Don't enable auto-trading until proven

# 4. Place ONE test trade
# Monitor closely

# 5. Verify fill and position
curl http://localhost:8001/positions

# 6. Check fees match calculation
curl http://localhost:8001/portfolio/fills
```

### Common Test Scenarios

#### Test Bracket Arbitrage

```python
# Simulate mutually exclusive brackets
brackets = [
    {"ticker": "A", "yes_ask": 25, "no_ask": 80},
    {"ticker": "B", "yes_ask": 30, "no_ask": 75},
    {"ticker": "C", "yes_ask": 20, "no_ask": 85},
]

# All YES: 25 + 30 + 20 = 75¢ (arb! profit = 25¢ - fees)
# All NO: 80 + 75 + 85 = 240¢ (no arb, need < 200¢)
# Min 2-NO: 75 + 80 = 155¢ (no arb, need < 100¢)
```

#### Test Position Constraint

```python
# Should fail
await place_order("TICKER", "yes", "buy", 10, 50)
await place_order("TICKER", "no", "buy", 10, 50)  # ERROR

# Should succeed
await place_order("TICKER-A", "yes", "buy", 10, 50)
await place_order("TICKER-B", "no", "buy", 10, 50)  # OK (different ticker)
```

#### Test Fee Calculation

```python
# Verify fees match Kalshi
assert calculate_fee(10, 50) == 2  # ceil(0.07 × 10 × 0.5 × 0.5) = 2
assert calculate_fee(100, 60) == 17  # ceil(0.07 × 100 × 0.6 × 0.4) = 17
```

---

## Additional Resources

### Context Documentation

For comprehensive codebase documentation, see:

- **[context/INDEX.md](context/INDEX.md)** - Complete file tree and module descriptions
- **[context/API.md](context/API.md)** - Full API reference for all functions/classes
- **[context/SCHEMAS.md](context/SCHEMAS.md)** - Database schemas and data models

### External Documentation

- [Kalshi API Docs](https://docs.kalshi.com/) - Official API reference
- [Kalshi Markets](https://kalshi.com/markets) - Browse available markets
- [NWS API](https://www.weather.gov/documentation/services-web-api) - Weather forecast API

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-01-09 | Initial comprehensive documentation |

---

**Last Updated**: 2024-01-09
**Maintained By**: AI Development Team
