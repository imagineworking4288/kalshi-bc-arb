# Kalshi Trading Platform - API Reference

## Overview

Complete API reference for the Kalshi Arbitrage Trading Platform including REST endpoints, core classes, and external API integrations.

**Last Updated**: 2026-01-15

---

## REST Endpoints (72 Total)

### Health & Configuration

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/health` | `main.health` | System health check |
| GET | `/api/config` | `get_config` | Trading configuration |
| GET | `/api/spot-price` | `get_spot_price` | Current BTC spot price |

### Arbitrage & Opportunities

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/opportunities` | `get_opportunities` | Get arbitrage opportunities |

### Trading Operations

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/balance` | `get_balance` | Account balance |
| GET | `/api/positions` | `get_positions` | Current positions |
| POST | `/api/execute` | `execute_arbitrage` | Execute arbitrage trade |
| POST | `/api/trade/place` | `place_trade` | Place manual trade |
| GET | `/api/trade/market/{ticker}` | `get_market_details` | Market details |

### Paper Trading

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| POST | `/api/paper/reset` | `reset_paper` | Reset paper account |
| GET | `/api/paper/summary` | `paper_summary` | Paper trading summary |
| GET | `/api/paper/trades` | `paper_trades` | Paper trade history |
| POST | `/api/paper/settle/{position_id}` | `settle_position` | Settle paper position |

### Execution Audit

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/executions` | `get_executions` | List execution audits |
| GET | `/api/executions/{audit_id}` | `get_execution` | Get specific audit |

### Portfolio

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/portfolio/summary` | `get_portfolio_summary` | Portfolio summary |
| GET | `/api/portfolio/positions` | `get_portfolio_positions` | Portfolio positions |
| GET | `/api/portfolio/orders` | `get_portfolio_orders` | Portfolio orders |

### Watchlist

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/watchlist` | `get_watchlist` | Get watchlist |
| POST | `/api/watchlist` | `add_to_watchlist` | Add to watchlist |
| DELETE | `/api/watchlist/{ticker}` | `remove_from_watchlist` | Remove from watchlist |

### Strategy Orchestrator (Main Trading Engine)

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/orchestrator/status` | `get_orchestrator_status` | Orchestrator status |
| POST | `/api/orchestrator/start` | `start_orchestrator` | Start orchestrator |
| POST | `/api/orchestrator/stop` | `stop_orchestrator` | Stop orchestrator |
| POST | `/api/orchestrator/auto-trade` | `set_orchestrator_auto_trade` | Enable/disable auto-trade |
| POST | `/api/orchestrator/mode` | `set_orchestrator_mode` | Set trading mode |
| POST | `/api/orchestrator/strategy/{strategy_type}/enable` | `enable_strategy` | Enable strategy |
| POST | `/api/orchestrator/scan` | `trigger_manual_scan` | Manual scan |
| POST | `/api/orchestrator/execute/{signal_id}` | `execute_signal` | Execute signal |
| POST | `/api/orchestrator/config` | `save_orchestrator_config` | Save config |

### Signals

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/signals` | `get_signals_v2` | Get all signals |
| GET | `/api/signals/stats` | `get_signal_stats` | Signal statistics |

### Performance

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/performance/metrics` | `get_performance_metrics` | Performance metrics |
| GET | `/api/performance/daily` | `get_daily_pnl` | Daily P&L |
| GET | `/api/performance/trades` | `get_trade_history` | Trade history |

### Circuit Breaker

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/circuit-breaker/status` | `get_circuit_breaker_status` | Circuit breaker status |
| POST | `/api/circuit-breaker/reset` | `reset_circuit_breaker` | Reset circuit breaker |
| POST | `/api/circuit-breaker/trip` | `trip_circuit_breaker` | Manually trip breaker |

### Emergency

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| POST | `/api/emergency/kill` | `emergency_kill` | Emergency stop |
| POST | `/api/emergency/resume` | `emergency_resume` | Resume trading |
| GET | `/api/emergency/status` | `emergency_status` | Emergency status |

### Risk Management

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/risk/status` | `get_risk_status` | Risk manager status |
| POST | `/api/risk/sync` | `sync_risk_positions` | Sync positions |

### Alerts

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/alerts` | `get_alerts` | Get alerts |
| GET | `/api/alerts/unacknowledged` | `get_unacknowledged_alerts` | Unacknowledged alerts |
| POST | `/api/alerts/{alert_id}/acknowledge` | `acknowledge_alert` | Acknowledge alert |
| POST | `/api/alerts/acknowledge-all` | `acknowledge_all_alerts` | Acknowledge all |
| GET | `/api/alerts/stats` | `get_alert_stats` | Alert statistics |

### Fee Calculator

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/fees/calculate` | `calculate_fee` | Calculate trade fee |
| GET | `/api/fees/table` | `get_fee_table` | Fee table |
| POST | `/api/fees/analyze-arbitrage` | `analyze_arbitrage_fees` | Analyze arb fees |

### Weather Predictions

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/predictions/cities` | `get_supported_cities` | Supported cities |
| GET | `/api/predictions/{city}` | `get_city_predictions` | City predictions |
| GET | `/api/predictions/{city}/forecast` | `get_city_forecast` | City forecast |
| POST | `/api/predictions/{city}/refresh` | `refresh_city_forecast` | Refresh forecast |
| POST | `/api/predictions/analyze` | `analyze_custom_brackets` | Analyze brackets |
| GET | `/api/predictions/status` | `get_prediction_status` | Prediction status |

### Scanners & BTC/Weather (Legacy)

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| GET | `/api/scanners/status` | `get_all_scanners_status` | All scanners status |
| GET | `/api/btc-arb/status` | `get_btc_arb_status` | BTC arb status |
| GET | `/api/weather-arb/status` | `get_weather_arb_status` | Weather arb status |

### Backtesting

| Method | Route | Handler | Description |
|--------|-------|---------|-------------|
| POST | `/api/backtest/run` | `run_backtest` | Run backtest |

---

## Core Classes Reference

### StrategyOrchestrator

**File**: `backend/services/core/strategy_orchestrator.py` (626 lines)

Main trading engine coordinating all strategies.

```python
class StrategyOrchestrator:
    def __init__(
        self, db, signals: SignalManager, kelly: KellySizing,
        risk: RiskManager, circuit: CircuitBreaker, executor: BatchExecutor,
        performance: PerformanceTracker, alerts: AlertService
    )

    # Lifecycle
    async def start() -> None
    async def stop() -> None

    # Strategy Management
    def register(strategy: BaseStrategy) -> None
    def unregister(strategy_type: StrategyType) -> bool
    def enable_strategy(strategy_type: StrategyType, enabled: bool) -> bool

    # Trading Control
    def set_auto_trade(enabled: bool) -> None
    def set_mode(mode: str) -> None  # "paper" or "live"

    # Execution
    async def scan_all() -> List[TradingSignal]
    async def manual_scan(strategy_type: Optional[StrategyType]) -> List[dict]
    async def manual_execute(signal_id: str) -> dict

    # Status
    def get_status() -> dict
    async def load_config() -> None
    async def save_config() -> None
```

### ExecutionGateway

**File**: `backend/services/core/execution_gateway.py` (1,208 lines)

Single entry point for ALL trade execution.

```python
class ExecutionGateway:
    def __init__(
        self, kalshi_client, paper_service, risk_manager, circuit_breaker,
        fee_calculator, db, alert_service, config: GatewayConfig = None,
        position_manager: PositionManager = None
    )

    # Main Execution
    async def execute(request: ExecutionRequest) -> ExecutionResult
    async def execute_single(
        ticker: str, side: str, action: str, contracts: int,
        price_cents: int, mode: str = "paper", source: str = "manual"
    ) -> ExecutionResult
    async def execute_arbitrage(
        legs: List[dict], contracts_per_leg: int,
        mode: str = "paper", source: str = "strategy"
    ) -> ExecutionResult

    # Validation (internal)
    async def _check_position_conflicts(request: ExecutionRequest) -> None
    async def _revalidate_prices(request: ExecutionRequest, max_slippage: int = 2) -> bool
    async def _check_market_open(ticker: str, min_seconds: int = 60) -> bool

    # Status
    def get_status() -> dict
    async def get_recent_audits(limit: int = 50) -> List[dict]
    def clear_cache() -> int

# KNOWN BUG at lines 294-297:
# Cache only invalidates when result.success=True
# Partial fills leave 30s stale data
```

### BatchExecutor

**File**: `backend/services/core/batch_executor.py` (421 lines)

Atomic multi-leg order execution.

```python
class BatchExecutor:
    def __init__(
        self, kalshi_client, paper_service: PaperTradingService = None,
        fee_calculator: FeeCalculator = None
    )

    async def execute(
        legs: List[OrderLeg], mode: str = "paper", atomic: bool = True
    ) -> BatchResult

    async def execute_arbitrage(
        legs_data: List[dict], contracts_per_leg: int, mode: str = "paper"
    ) -> BatchResult

    async def execute_single(
        ticker: str, side: str, action: str, contracts: int,
        price_cents: int, mode: str = "paper"
    ) -> BatchResult

    def estimate_cost(legs: List[OrderLeg]) -> dict

# KNOWN BUG at lines 255-290:
# No rollback logic for partial fills
# When one leg fails in live mode, successful legs are not rolled back
```

### WeatherStrategy

**File**: `backend/services/strategies/weather_strategy.py` (631 lines)

Weather bracket arbitrage strategy.

```python
class WeatherStrategy(BaseStrategy):
    strategy_type = StrategyType.WEATHER

    def __init__(
        self, kalshi_client, nws_client: Optional[NWSClient] = None,
        min_edge_percent: float = 3.0, min_directional_edge: float = 5.0,
        scan_interval: float = 30.0
    )

    @property
    def scan_interval_seconds(self) -> float  # 30 seconds

    async def scan() -> List[TradingSignal]
    async def validate_signal(signal: TradingSignal) -> bool

    # Internal methods
    async def _get_forecast(location: LocationConfig) -> Optional[dict]
    async def _fetch_series_markets(series_ticker: str) -> List[dict]
    def _check_bracket_arbitrage(...) -> List[TradingSignal]
    def _check_directional_opportunities(...) -> List[TradingSignal]
    def _calculate_bracket_probability(...) -> float

# CRITICAL BUG at lines 333-338:
# edge_percent = (100 - total_yes) / total_yes * 100
# Does NOT call FeeCalculator - shows inflated edge
# Example: Shows 2.04% edge when actual is -6.54% after fees
```

### FeeCalculator

**File**: `backend/services/core/fee_calculator.py` (602 lines)

Kalshi fee calculation service.

```python
class FeeCalculator:
    TAKER_RATE: float = 0.07    # 7%
    MAKER_RATE: float = 0.035   # 3.5%
    MIN_FEE_PER_CONTRACT: int = 1

    def calculate(
        contracts: int, price_cents: int, fee_type: FeeType = FeeType.TAKER
    ) -> FeeCalculation

    def calculate_multi_leg(
        legs: List[dict], fee_type: FeeType = FeeType.TAKER
    ) -> dict

    def estimate_arbitrage_profit(
        legs: List[dict], payout_cents: int = 100, fee_type: FeeType = FeeType.TAKER
    ) -> dict

    def analyze_weather_arbitrage(
        yes_asks: List[int], no_asks: List[int], fee_type: FeeType = FeeType.TAKER
    ) -> dict

    # Class methods (backwards compatible)
    @classmethod
    def fee_per_contract(price_cents: int, fee_type: FeeType = FeeType.TAKER) -> float
    @classmethod
    def calculate_trade_fee(price_cents: int, contracts: int, ...) -> FeeBreakdown
```

### PositionManager

**File**: `backend/services/core/position_manager.py` (597 lines)

Unified position tracking across paper/live modes.

```python
class PositionManager:
    def __init__(
        self, kalshi_client, db, config: PositionConfig = None
    )

    async def get_positions(
        mode: str = "paper", force_refresh: bool = False
    ) -> List[UnifiedPosition]

    async def get_position(
        ticker: str, mode: str = "paper", force_refresh: bool = False
    ) -> Optional[UnifiedPosition]

    async def has_position(
        ticker: str, mode: str = "paper", side: Optional[str] = None
    ) -> bool

    async def can_open_position(
        ticker: str, side: str, mode: str = "paper"
    ) -> Tuple[bool, str]  # Validates YES+NO constraint

    async def get_exposure(mode: str = "paper") -> ExposureSummary

    def invalidate_cache() -> None  # Clear live position cache

    def get_status() -> dict
```

### RiskManager

**File**: `backend/services/core/risk_manager.py` (330 lines)

Position limits and loss tracking.

```python
class RiskManager:
    def __init__(self, limits: RiskLimits, db)

    def check_trade(
        ticker: str, contracts: int, price_cents: int, balance_cents: int
    ) -> RiskCheck

    def record_trade(ticker: str, contracts: int, price_cents: int) -> None
    def record_pnl(pnl_cents: int) -> None
    def close_position(ticker: str, contracts: int) -> None
    def get_status() -> dict
    def sync_positions(positions: List) -> None

@dataclass
class RiskLimits:
    max_position_per_market: int = 100
    max_total_position: int = 500
    max_daily_loss_cents: int = 5000
    max_single_trade_cents: int = 1000
```

### CircuitBreaker

**File**: `backend/services/core/circuit_breaker.py` (303 lines)

Emergency halt on consecutive losses.

```python
class CircuitBreaker:
    def __init__(self, config: CBConfig = None)

    def can_trade() -> Tuple[bool, Optional[str]]
    def record_result(won: bool, pnl_cents: int, ticker: str) -> None
    def reset() -> None
    def force_trip(reason: str) -> None
    def daily_reset() -> None
    def get_status() -> dict

@dataclass
class CBConfig:
    max_consecutive_losses: int = 5
    max_daily_loss_cents: int = 5000
    max_hourly_losses: int = 3
    cooldown_seconds: int = 300
```

### SignalManager

**File**: `backend/services/core/signal_manager.py` (374 lines)

Signal lifecycle management.

```python
class SignalManager:
    def __init__(self, db)

    async def create(signal: TradingSignal, expires_in: int = 300) -> TradingSignal
    async def get_pending(strategy_type: Optional[StrategyType], limit: int = 100) -> List[TradingSignal]
    async def get_by_id(signal_id: str) -> Optional[TradingSignal]
    async def update_status(signal_id: str, status: SignalStatus, notes: str = None, execution_price: int = None) -> bool
    async def has_recent(ticker: str, strategy_type: StrategyType, seconds: int = 300) -> bool
    async def expire_old() -> int
    async def get_history(strategy_type: Optional[StrategyType], status: Optional[SignalStatus], limit: int = 50) -> List[TradingSignal]
    async def get_stats(days: int = 7) -> dict
```

### KalshiClient

**File**: `backend/services/kalshi_client.py` (302 lines)

Kalshi REST API client with RSA-PSS authentication.

```python
class KalshiClient:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    async def get_markets(limit: int = 100) -> List[dict]
    async def get_market(ticker: str) -> dict
    async def get_orderbook(ticker: str, depth: int = 10) -> dict
    async def get_events(
        series_ticker: Optional[str] = None, status: str = "open",
        with_nested_markets: bool = True, limit: int = 100
    ) -> List[dict]
    async def get_balance() -> dict
    async def get_positions(status: str = "open") -> List[dict]
    async def place_order(
        ticker: str, side: str, action: str, count: int,
        price: int, order_type: str = "limit", client_order_id: str = None
    ) -> dict
    async def place_batch_orders(orders: List[dict]) -> dict
    async def get_fills(limit: int = 100) -> List[dict]
    async def get_orders(status: str = None, limit: int = 100) -> List[dict]
```

### BaseStrategy

**File**: `backend/services/core/base_strategy.py` (285 lines)

Abstract base for all strategies.

```python
class BaseStrategy(ABC):
    def __init__(self, strategy_type: StrategyType, name: str)

    @property
    @abstractmethod
    def scan_interval_seconds(self) -> float

    @abstractmethod
    async def scan(self) -> List[TradingSignal]

    @abstractmethod
    async def validate_signal(signal: TradingSignal) -> bool

    def get_status() -> dict
    async def run_scan() -> List[TradingSignal]  # With error handling

@dataclass
class TradingSignal:
    signal_id: str
    strategy_type: StrategyType
    ticker: str
    signal_type: SignalType
    edge_percent: float
    model_prob: float
    market_price: int
    recommended_size: int
    confidence: float
    is_arbitrage: bool
    legs: List[SignalLeg]
    metadata: dict
    created_at: datetime
    status: SignalStatus = SignalStatus.PENDING
```

---

## Data Classes

### Execution Models

```python
@dataclass
class ExecutionRequest:
    request_id: str
    source: str  # "strategy", "manual", "auto"
    mode: str  # "paper", "live"
    legs: List[ExecutionLeg]
    atomic: bool = True
    max_slippage_cents: int = 2

@dataclass
class ExecutionLeg:
    ticker: str
    side: str  # "yes", "no"
    action: str  # "buy", "sell"
    contracts: int
    price_cents: int

@dataclass
class ExecutionResult:
    request_id: str
    success: bool
    mode: str
    legs: List[LegResult]
    total_cost_cents: int
    total_fees_cents: int
    execution_time_ms: int
    audit_id: Optional[str] = None
    error: Optional[str] = None
```

### Batch Executor Models

```python
class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class OrderLeg:
    ticker: str
    side: OrderSide
    action: OrderAction
    contracts: int
    price_cents: int
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[int] = None
    filled_contracts: int = 0
    order_id: Optional[str] = None
    error: Optional[str] = None
    fee_cents: int = 0

@dataclass
class BatchResult:
    success: bool
    batch_id: str
    legs: List[OrderLeg]
    total_cost_cents: int = 0
    total_fees_cents: int = 0
    execution_time_ms: int = 0
    message: str = ""
    mode: str = "paper"
```

### Fee Calculator Models

```python
class FeeType(Enum):
    TAKER = "taker"  # 7%
    MAKER = "maker"  # 3.5%

@dataclass
class FeeCalculation:
    gross_cost_cents: int
    fee_cents: int
    total_cost_cents: int
    fee_type: FeeType
    fee_rate: float
```

---

## Kalshi API Reference

### Base URL
```
https://api.elections.kalshi.com/trade-api/v2
```

### Authentication
RSA-PSS signature with SHA-256.

```python
# Headers required
KALSHI-ACCESS-KEY: <api_key_id>
KALSHI-ACCESS-TIMESTAMP: <unix_ms>
KALSHI-ACCESS-SIGNATURE: <base64_signature>
Content-Type: application/json

# Signature
timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
message = f"{timestamp}GET/trade-api/v2/markets"  # No query params

signature = private_key.sign(
    message.encode(),
    padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH  # NOT MAX_LENGTH
    ),
    hashes.SHA256()
)
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/markets` | GET | List markets |
| `/markets/{ticker}` | GET | Single market |
| `/markets/{ticker}/orderbook` | GET | Order book |
| `/events` | GET | Events with markets |
| `/portfolio/balance` | GET | Account balance |
| `/portfolio/positions` | GET | Current positions |
| `/portfolio/orders` | POST | Place order |
| `/portfolio/orders/batched` | POST | Batch orders |

### Rate Limits

| Tier | Limit |
|------|-------|
| Free | 10 req/sec |
| Standard | 30 req/sec |
| Premium | 100 req/sec |

---

## Fee Calculation

### Formula
```python
fee = ceil(rate * contracts * (price/100) * (1 - price/100) * 100)
```

### Examples
| Contracts | Price | Type | Fee |
|-----------|-------|------|-----|
| 10 | 50¢ | Taker | 18¢ |
| 10 | 60¢ | Taker | 17¢ |
| 10 | 30¢ | Maker | 8¢ |
| 100 | 50¢ | Taker | 175¢ |

---

## Known Bugs in API Layer

| Bug | Location | Impact |
|-----|----------|--------|
| Fee not in edge calc | `weather_strategy.py:333-338` | Inflated edge (2.04% vs -6.54% real) |
| No partial rollback | `batch_executor.py:255-290` | Unhedged positions |
| Cache invalidation | `execution_gateway.py:294-297` | 30s stale data on partial fills |
