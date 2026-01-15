# SCHEMAS.md - Data Schemas Reference

> Database tables and core data classes for the Kalshi Arbitrage Platform

---

## Database Schema (SQLite)

### Paper Trading Tables

#### `paper_account`
Single-row table tracking paper trading balance.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Always 1 |
| balance | REAL | Current balance in **dollars** |
| starting_balance | REAL | Initial balance in **dollars** |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**⚠️ Important**: Balance stored in DOLLARS. Multiply by 100 for API (cents).

#### `paper_positions`
Individual position records from paper trades.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT | Primary key |
| ticker | TEXT | Market ticker |
| side | TEXT | 'yes' or 'no' |
| contracts | INTEGER | Position size |
| avg_price | REAL | Average entry price |
| total_cost | REAL | Total cost including fees |
| total_fees | REAL | Fees paid |
| settlement_time | TIMESTAMP | When market settles |
| settled | INTEGER | 0=open, 1=settled |
| realized_pnl | REAL | P&L after settlement |
| trade_id | TEXT | FK to paper_trades |

#### `paper_trades`
Grouped arbitrage executions (multiple positions per trade).

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT | Primary key |
| asset | TEXT | Underlying asset |
| total_cost | REAL | Sum of leg costs |
| expected_profit | REAL | Calculated profit |
| expected_profit_pct | REAL | Profit percentage |
| legs_json | TEXT | JSON array of legs |
| status | TEXT | 'open', 'settled', 'partial' |

---

### Trading Signals Tables

#### `signals_v2`
Unified signals table for all strategies.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT | UUID primary key |
| strategy_type | TEXT | 'weather', 'btc', 'economic' |
| ticker | TEXT | Target market |
| signal_type | TEXT | 'directional', 'arbitrage', 'spread' |
| edge_percent | REAL | Calculated edge |
| model_prob | REAL | Model's probability |
| market_price | INTEGER | Current price (cents) |
| recommended_size | INTEGER | Suggested contracts |
| confidence | REAL | Signal confidence (0-1) |
| is_arbitrage | INTEGER | 1 if multi-leg arb |
| legs_json | TEXT | JSON array for multi-leg |
| status | TEXT | 'pending', 'executing', 'executed', 'rejected', 'expired', 'failed' |
| created_at | TIMESTAMP | Signal generation time |
| expires_at | TIMESTAMP | Auto-expire time |

#### `trade_records`
Execution records for performance tracking.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT | UUID primary key |
| strategy_type | TEXT | Source strategy |
| ticker | TEXT | Market ticker |
| side | TEXT | 'yes' or 'no' |
| contracts | INTEGER | Size |
| entry_price | INTEGER | Entry in cents |
| exit_price | INTEGER | Exit in cents (if closed) |
| pnl_cents | INTEGER | Realized P&L |
| status | TEXT | 'open', 'closed', 'settled' |
| batch_id | TEXT | Groups multi-leg trades |
| signal_id | TEXT | FK to signals_v2 |

---

### Risk Management Tables

#### `circuit_breaker_state`
Persistent circuit breaker state (single row).

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Always 1 |
| tripped | INTEGER | 0=normal, 1=tripped |
| trip_reason | TEXT | Why breaker tripped |
| permanent | INTEGER | 1=requires manual reset |
| consecutive_losses | INTEGER | Loss streak count |
| daily_loss_cents | INTEGER | Today's loss |
| hourly_trades_json | TEXT | Rate limit tracking |
| last_reset_date | TEXT | YYYY-MM-DD |

#### `daily_pnl_v2`
Daily P&L tracking with win/loss stats.

| Column | Type | Notes |
|--------|------|-------|
| date | TEXT | YYYY-MM-DD (primary key) |
| realized_pnl_cents | INTEGER | Closed P&L |
| unrealized_pnl_cents | INTEGER | Open P&L |
| total_trades | INTEGER | Trade count |
| winning_trades | INTEGER | Wins |
| losing_trades | INTEGER | Losses |
| max_drawdown_cents | INTEGER | Peak to trough |

#### `orchestrator_config`
Trading orchestrator settings (single row).

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Always 1 |
| auto_trade_enabled | INTEGER | 0=off, 1=on |
| mode | TEXT | 'paper' or 'live' |
| kelly_fraction | REAL | Kelly multiplier (default 0.25) |
| min_edge_percent | REAL | Minimum edge to trade |
| max_position_per_market | INTEGER | Position limit |
| max_daily_loss_cents | INTEGER | Daily loss limit |

---

### Execution Audit Table

#### `execution_audit`
Complete audit trail for all trade executions.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT | UUID primary key |
| request_id | TEXT | Unique request identifier |
| source | TEXT | 'orchestrator', 'manual', 'btc_arb', 'weather_arb', 'strategy' |
| signal_id | TEXT | FK to originating signal |
| mode | TEXT | 'paper', 'live', 'dual' |
| legs_json | TEXT | JSON array of leg requests |
| atomic | INTEGER | 1=all-or-nothing |
| success | INTEGER | 1=success, 0=failure |
| total_cost_cents | INTEGER | Total execution cost |
| execution_time_ms | INTEGER | Execution duration |
| leg_results_json | TEXT | Per-leg outcomes |
| error | TEXT | Error message if failed |

---

### Strategy-Specific Tables

#### `btc_arb_executions`
BTC arbitrage trade records.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT | Primary key |
| opportunity_id | TEXT | Source opportunity |
| mode | TEXT | 'paper' or 'live' |
| contracts_per_leg | INTEGER | Size per leg |
| guaranteed_profit_cents | INTEGER | Expected profit |
| status | TEXT | 'open', 'settled', 'partial', 'failed' |
| actual_profit_cents | INTEGER | Realized profit |
| audit_id | TEXT | FK to execution_audit |

#### `btc_arb_config`
BTC arbitrage scanner settings.

| Column | Type | Notes |
|--------|------|-------|
| min_edge_percent | REAL | Minimum edge (default 3.0) |
| default_budget_cents | INTEGER | Default trade size |
| auto_trade_enabled | INTEGER | Auto-execution flag |
| scan_interval_seconds | REAL | Scan frequency |
| mode | TEXT | 'paper' or 'live' |

---

## Core Data Classes (Pydantic)

### Execution Types

```python
@dataclass
class ExecutionLeg:
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    count: int
    price_cents: int  # 1-99

@dataclass
class ExecutionRequest:
    request_id: str
    legs: List[ExecutionLeg]
    mode: Literal["paper", "live", "dual"]
    atomic: bool = True
    max_slippage_cents: int = 2
    source: str = "manual"

@dataclass
class LegResult:
    ticker: str
    success: bool
    filled_count: int
    avg_price: float
    fees_cents: int
    error: Optional[str]

@dataclass
class ExecutionResult:
    request_id: str
    success: bool
    total_cost_cents: int
    total_fees_cents: int
    leg_results: List[LegResult]
    execution_time_ms: int
    error: Optional[str]
```

### Signal Types

```python
@dataclass
class TradingSignal:
    id: str
    strategy_type: str
    ticker: str
    signal_type: str
    edge_percent: float
    model_prob: float
    market_price: int
    recommended_size: int
    confidence: float = 1.0
    is_arbitrage: bool = False
    legs: Optional[List[ExecutionLeg]] = None
    metadata: Optional[Dict] = None
    expires_at: Optional[datetime] = None
```

### Market Types

```python
@dataclass
class Market:
    ticker: str
    title: str
    subtitle: str
    event_ticker: str
    yes_ask: int  # cents
    yes_bid: int
    no_ask: int
    no_bid: int
    volume: int
    open_interest: int
    settlement_time: datetime
    floor_strike: Optional[float]
    cap_strike: Optional[float]
    status: str

@dataclass
class BracketMarket:
    ticker: str
    lower_bound: Optional[float]  # None = open-ended low
    upper_bound: Optional[float]  # None = open-ended high
    yes_ask: int
    no_ask: int
    label: str  # e.g., "60-61" or "≥70"
```

### Arbitrage Types

```python
@dataclass
class ArbitrageOpportunity:
    id: str
    strategy: Literal["all_yes", "all_no", "min_2_no"]
    brackets: List[BracketMarket]
    total_cost_cents: int
    guaranteed_payout_cents: int
    profit_cents: int
    profit_percent: float
    fees_cents: int
    net_profit_cents: int
    net_profit_percent: float
    max_contracts: int
    expires_at: datetime

@dataclass
class ExecutedArbitrage:
    opportunity_id: str
    execution_result: ExecutionResult
    contracts_per_leg: int
    expected_profit_cents: int
    status: str
```

---

## Fee Calculation Formula

```python
def calculate_fee(contracts: int, price_cents: int, rate: float = 0.07) -> int:
    """
    Kalshi fee formula:
    fee = ceil(rate * contracts * (price/100) * (1 - price/100) * 100)

    Example: 10 contracts at 60¢
    fee = ceil(0.07 * 10 * 0.60 * 0.40 * 100) = ceil(16.8) = 17¢
    """
    price = price_cents / 100.0
    raw_fee = rate * contracts * price * (1 - price) * 100
    return max(1, math.ceil(raw_fee))
```

**⚠️ Known Bug**: `weather_strategy.py:333-338` does NOT use fee calculator, showing inflated edges.

---

## Key Relationships

```
signals_v2 ──────────────┐
    │                    │
    ▼                    ▼
trade_records ◄──── execution_audit
    │                    │
    ▼                    │
daily_pnl_v2            │
                        │
btc_arb_executions ◄────┘
```

---

## Scanner Database (`scanner_results.db`)

Separate database for scanner output (write-heavy).

#### `scanner_results`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT | Primary key |
| scanner_type | TEXT | 'btc_arb', 'weather_arb' |
| data_json | TEXT | Serialized opportunities |
| created_at | TIMESTAMP | Scan timestamp |

#### `scanner_stats`
| Column | Type | Notes |
|--------|------|-------|
| scanner_type | TEXT | Primary key |
| last_scan | TIMESTAMP | Last successful scan |
| opportunities_found | INTEGER | Count |
| scan_duration_ms | INTEGER | Performance metric |

---

*Last updated: 2025-01-15*
