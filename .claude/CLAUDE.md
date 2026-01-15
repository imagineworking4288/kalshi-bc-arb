# CLAUDE.md - Kalshi Arbitrage Platform

> AI Assistant Reference for the Kalshi prediction market arbitrage trading platform.

---

## 1. Project Overview

**Purpose**: Automated prediction market arbitrage detection and execution on Kalshi.

### Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | FastAPI | REST API + WebSocket |
| Frontend | React + TypeScript | Web UI |
| Database | SQLite + aiosqlite | Local persistence |
| Auth | RSA-PSS (SHA-256) | Kalshi API signing |
| HTTP | httpx | Async HTTP client |

### Trading Modes

| Mode | Description | Status |
|------|-------------|--------|
| **Live** | Real Kalshi API trading | Active |
| **Demo** | Simulated trading | Phase 2 |

### Supported Markets

- **Weather**: High/Low temperature brackets (6 cities)
- **BTC**: Price threshold and range markets

---

## 2. Critical Constraints

### Position Limitation (MOST IMPORTANT)

**Kalshi does NOT allow holding YES and NO on the same market simultaneously.**

```python
# INVALID - Will fail
buy_yes("KXBTC-25JAN15-100000")
buy_no("KXBTC-25JAN15-100000")  # ERROR!

# VALID - Different tickers
buy_yes("KXBTC-25JAN15-100000-100499")  # Range market
buy_no("KXBTCD-25JAN15-100000")         # Threshold market
```

### Rate Limits

| Tier | Limit | Use Case |
|------|-------|----------|
| Free | 10/sec | Scanning |
| Standard | 30/sec | Live trading |
| Premium | 100/sec | High-frequency |

### Ports

| Service | Port |
|---------|------|
| Backend | 8001 |
| Frontend | 5173 |

---

## 3. Architecture

### Single-Process Design

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Backend                       │
│  ┌─────────┐   ┌──────────┐   ┌───────────┐   ┌──────┐ │
│  │ Scanner │──►│ Signal   │──►│ Execution │──►│ Pos  │ │
│  │ Service │   │ Manager  │   │ Gateway   │   │ Mgr  │ │
│  └─────────┘   └──────────┘   └───────────┘   └──────┘ │
│       │              │              │              │     │
│       └──────────────┴──────────────┴──────────────┘     │
│                          │                               │
│                    ┌─────▼─────┐                         │
│                    │  SQLite   │                         │
│                    └───────────┘                         │
└─────────────────────────────────────────────────────────┘
         ▲                                    │
         │ REST/WS                            │ HTTP
         │                                    ▼
┌────────┴────────┐                  ┌────────────────┐
│  React Frontend │                  │  Kalshi API    │
└─────────────────┘                  └────────────────┘
```

### Signal Lifecycle

```
DETECTED → VALIDATED → EXECUTING → EXECUTED → SETTLED
    │          │           │           │          │
    │          │           │           │          └─ Final P&L recorded
    │          │           │           └─ Position opened
    │          │           └─ Orders placed with Kalshi
    │          └─ Passes risk checks, has edge
    └─ Scanner found opportunity
```

### Data Flow

1. **Scanner** detects arbitrage opportunity
2. **SignalManager** validates edge and creates signal
3. **RiskManager** checks limits, circuit breaker
4. **ExecutionGateway** places orders via Kalshi API
5. **PositionManager** tracks open positions
6. **Settlement** resolves P&L at market close

---

## 4. File Structure

```
kalshi-arb/
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Pydantic settings
│   ├── exceptions.py           # Custom exceptions
│   ├── api/
│   │   ├── routes/
│   │   │   ├── trading.py      # /execute, /positions
│   │   │   ├── signals.py      # /signals, /opportunities
│   │   │   ├── risk.py         # /circuit-breaker, /risk
│   │   │   ├── weather.py      # /weather-arb/*
│   │   │   └── btc.py          # /btc-arb/*
│   │   ├── middleware.py       # Auth, rate limiting
│   │   └── websocket/          # Phase 2
│   ├── core/
│   │   ├── client/
│   │   │   ├── kalshi.py       # Kalshi REST client
│   │   │   ├── auth.py         # RSA-PSS signing
│   │   │   └── nws.py          # Weather forecast API
│   │   ├── fees/
│   │   │   └── calculator.py   # Single fee source
│   │   ├── execution/
│   │   │   ├── gateway.py      # Trade execution
│   │   │   └── batch.py        # Multi-leg orders
│   │   ├── positions/
│   │   │   └── manager.py      # Position tracking
│   │   └── risk/
│   │       ├── circuit_breaker.py
│   │       ├── limits.py
│   │       └── manager.py
│   ├── scanners/
│   │   ├── base.py             # Scanner interface
│   │   ├── weather/
│   │   │   ├── scanner.py
│   │   │   └── strategy.py
│   │   └── btc/
│   │       ├── scanner.py
│   │       └── strategy.py
│   ├── signals/
│   │   ├── manager.py          # Signal lifecycle
│   │   └── models.py           # Signal types
│   ├── models/
│   │   ├── market.py           # Market, Orderbook
│   │   ├── execution.py        # ExecutionRequest/Result
│   │   └── position.py         # Position, Trade
│   └── database/
│       ├── connection.py
│       └── schema.sql
├── frontend/
│   └── src/
│       ├── components/
│       ├── services/api.ts
│       └── stores/
└── data/
    └── kalshi.db
```

---

## 5. API Reference

### Authentication

```python
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

# 1. Create message
timestamp = str(int(time.time() * 1000))
message = f"{timestamp}{method}{path}"  # e.g., "1234567890000GET/trade-api/v2/markets"

# 2. Sign with RSA-PSS
signature = private_key.sign(
    message.encode(),
    padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH  # NOT MAX_LENGTH
    ),
    hashes.SHA256()
)

# 3. Headers
headers = {
    "KALSHI-ACCESS-KEY": api_key_id,
    "KALSHI-ACCESS-TIMESTAMP": timestamp,
    "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode()
}
```

### Endpoints (~30 total)

#### Trading
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /execute | Execute arbitrage trade |
| GET | /positions | Get open positions |
| GET | /balance | Get account balance |

#### Signals
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /signals | List trading signals |
| GET | /opportunities | Current arb opportunities |
| GET | /signals/stats | Signal statistics |

#### Risk
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /circuit-breaker/status | CB state |
| POST | /circuit-breaker/reset | Reset CB |
| GET | /risk/status | Risk metrics |

#### Weather Arbitrage
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /weather-arb/status | Scanner status |
| GET | /weather-arb/city/{code} | City opportunities |

#### BTC Arbitrage
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /btc-arb/status | Scanner status |
| POST | /btc-arb/execute/{id} | Execute opportunity |

#### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /config | Current config |

---

## 6. Trading Strategies

### Bracket Arbitrage

**Concept**: Buy all outcomes in a mutually exclusive set when `total_cost < guaranteed_payout`.

#### Strategy 1: All YES
Buy YES on every bracket. Profit if `sum(yes_ask) < 100¢`.

```python
# 4 weather brackets
brackets = [25¢, 30¢, 20¢, 15¢]  # Total: 90¢
payout = 100¢  # Exactly ONE will be YES
profit = 10¢ - fees
```

#### Strategy 2: All NO
Buy NO on every bracket. Profit if `sum(no_ask) < (n-1) × 100¢`.

```python
# 4 brackets, (n-1)=3 will pay out
no_asks = [75¢, 70¢, 80¢, 85¢]  # Total: 310¢
payout = 300¢  # 3 NOs pay
# No profit (310 > 300)
```

#### Strategy 3: Min 2-NO
Buy 2 cheapest NOs. Profit if `no1 + no2 < 100¢`.

```python
cheapest = [35¢, 40¢]  # Total: 75¢
payout = 100¢  # Both pay if neither bracket wins
profit = 25¢ - fees
```

### Fee Calculation

```python
def calculate_fee(contracts: int, price_cents: int, rate: float = 0.07) -> int:
    """
    fee = ceil(rate × contracts × price × (1 - price))

    Example: 10 contracts at 60¢
    fee = ceil(0.07 × 10 × 0.60 × 0.40 × 100) = ceil(16.8) = 17¢
    """
    price = price_cents / 100.0
    raw = rate * contracts * price * (1 - price) * 100
    return max(1, math.ceil(raw))
```

### Weather Markets

| City | High Series | Low Series |
|------|-------------|------------|
| New York | KXHIGHNY | KXLOWNY |
| Los Angeles | KXHIGHLA | KXLOWLA |
| Chicago | KXHIGHCH | KXLOWCH |
| Miami | KXHIGHMI | KXLOWMI |
| Denver | KXHIGHDE | KXLOWDE |
| Austin | KXHIGHAU | KXLOWAU |

**Settlement**: NWS official high/low temperature at midnight local time.

### BTC Markets

- **KXBTC**: Range markets (e.g., $100,000-$100,499)
- **KXBTCD**: Threshold markets (e.g., ≥$100,000)

---

## 7. Database Schema (10 Tables)

### Core Tables

```sql
-- Signal tracking
CREATE TABLE signals_v2 (
    id TEXT PRIMARY KEY,
    strategy_type TEXT NOT NULL,      -- 'weather', 'btc'
    ticker TEXT NOT NULL,
    edge_percent REAL NOT NULL,
    status TEXT DEFAULT 'pending',    -- pending/executing/executed/settled
    created_at TIMESTAMP NOT NULL,
    executed_at TIMESTAMP,
    settled_at TIMESTAMP
);

-- Execution audit trail
CREATE TABLE execution_audit (
    id TEXT PRIMARY KEY,
    request_id TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,             -- 'scanner', 'manual'
    mode TEXT NOT NULL,               -- 'live', 'demo'
    legs_json TEXT NOT NULL,
    success INTEGER NOT NULL,
    total_cost_cents INTEGER,
    error TEXT
);

-- Risk management
CREATE TABLE circuit_breaker_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    tripped INTEGER DEFAULT 0,
    trip_reason TEXT,
    consecutive_losses INTEGER DEFAULT 0,
    daily_loss_cents INTEGER DEFAULT 0,
    last_reset_date TEXT
);

-- Position tracking
CREATE TABLE positions (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    contracts INTEGER NOT NULL,
    avg_price_cents INTEGER NOT NULL,
    status TEXT DEFAULT 'open'
);

-- Trade records
CREATE TABLE trade_records (
    id TEXT PRIMARY KEY,
    signal_id TEXT REFERENCES signals_v2(id),
    ticker TEXT NOT NULL,
    entry_price_cents INTEGER NOT NULL,
    exit_price_cents INTEGER,
    pnl_cents INTEGER,
    status TEXT DEFAULT 'open'
);
```

### Config Tables

```sql
-- Risk limits
CREATE TABLE risk_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    max_position_per_market INTEGER DEFAULT 100,
    max_daily_loss_cents INTEGER DEFAULT 5000,
    min_edge_percent REAL DEFAULT 3.0
);

-- Scanner config
CREATE TABLE scanner_config (
    scanner_type TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 1,
    scan_interval_seconds REAL DEFAULT 30.0
);
```

---

## 8. Quick Commands

### Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install

# Environment
cp .env.example .env
# Edit .env with Kalshi credentials
```

### Start (2 Terminals)

```bash
# Terminal 1: Backend
uvicorn backend.main:app --reload --port 8001

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Common Operations

```bash
# Health check
curl http://localhost:8001/health

# View opportunities
curl http://localhost:8001/opportunities

# Check circuit breaker
curl http://localhost:8001/circuit-breaker/status

# Execute trade (POST)
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{"signal_id": "abc123"}'
```

---

## 9. Known Issues / Deferred

### Deferred to Phase 2

| Feature | Status | Notes |
|---------|--------|-------|
| Paper/Demo mode | Deferred | Live mode only for now |
| Backtesting engine | Deferred | Use historical data manually |
| Alert service | Deferred | Check logs for now |
| WebSocket streaming | Deferred | Use REST polling |

### Phase 2 Roadmap

- [ ] WebSocket real-time updates
- [ ] Demo mode with simulated fills
- [ ] Additional markets (economic events)
- [ ] Mobile-responsive UI
- [ ] Performance dashboard

### Active Bugs to Fix

| Bug | Location | Priority |
|-----|----------|----------|
| Fee not in weather edge calc | `scanners/weather/strategy.py` | P0 |
| No partial fill rollback | `core/execution/batch.py` | P0 |
| Cache stale on partial | `core/execution/gateway.py` | P1 |

---

## Environment Variables

```bash
# Required
KALSHI_API_KEY_ID=your-key-id
KALSHI_PRIVATE_KEY_PATH=./keys/private.pem

# Optional
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
LOG_LEVEL=INFO
DATABASE_PATH=./data/kalshi.db
```

---

*Last Updated: 2026-01-15*
