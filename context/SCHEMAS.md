# Data Schemas

## Configuration

### Settings (backend/config/__init__.py)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| kalshi_api_key_id | str | "" | API key ID from Kalshi dashboard |
| kalshi_private_key_path | str | "./kalshi_private_key.pem" | Path to RSA private key file |
| kalshi_base_url | str | "https://api.elections.kalshi.com/trade-api/v2" | Kalshi production API endpoint |
| kalshi_ws_url | str | "wss://api.elections.kalshi.com/trade-api/ws/v2" | Kalshi WebSocket endpoint |
| paper_trading | bool | True | True for simulation, False for real money |
| paper_trading_mode | bool | True | Alias for compatibility |
| initial_paper_balance | int | 10000 | Initial paper balance in cents |
| paper_starting_balance | float | 10000.00 | Initial paper balance in dollars (compatibility) |
| btc_scan_interval | float | 2.0 | BTC scanner interval in seconds |
| weather_scan_interval | float | 30.0 | Weather scanner interval in seconds |
| database_path | str | "./data/kalshi.db" | SQLite database file path |
| scanner_db_path | str | "./data/scanner_results.db" | Scanner results database path |
| log_level | str | "INFO" | Logging verbosity level |

---

## Database Tables (backend/database/schema.sql)

### paper_account

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Always 1, single row table |
| balance | REAL | Current paper account balance |
| starting_balance | REAL | Balance at last reset |
| created_at | TIMESTAMP | Account creation time |
| updated_at | TIMESTAMP | Last modification time |

### paper_positions

| Field | Type | Description |
|-------|------|-------------|
| id | TEXT PRIMARY KEY | UUID position identifier |
| created_at | TIMESTAMP | Position open time |
| ticker | TEXT | Kalshi market ticker |
| side | TEXT | 'yes' or 'no' position side |
| contracts | INTEGER | Number of contracts held |
| avg_price | REAL | Average entry price 0.0-1.0 |
| total_cost | REAL | Total cost in dollars |
| total_fees | REAL | Total fees paid |
| settlement_time | TIMESTAMP | Market settlement time |
| settled | INTEGER | 0 = open, 1 = settled |
| settled_at | TIMESTAMP | When position was settled |
| settlement_value | REAL | Final settlement price |
| realized_pnl | REAL | Realized profit/loss |
| trade_id | TEXT | Parent trade group ID |

### paper_trades

| Field | Type | Description |
|-------|------|-------------|
| id | TEXT PRIMARY KEY | UUID trade identifier |
| executed_at | TIMESTAMP | Trade execution time |
| asset | TEXT | Asset symbol (e.g., "BTC") |
| total_cost | REAL | Sum of all leg costs |
| total_fees | REAL | Sum of all leg fees |
| contracts_per_leg | INTEGER | Contracts bought per bracket |
| expected_payout | REAL | Guaranteed payout ($1 per set) |
| expected_profit | REAL | Expected net profit |
| expected_profit_pct | REAL | Expected profit percentage |
| actual_payout | REAL | Actual payout after settlement |
| actual_profit | REAL | Actual realized profit |
| legs_json | TEXT | JSON array of order details |
| status | TEXT | 'open', 'settled', or 'partial' |

### opportunity_history

| Field | Type | Description |
|-------|------|-------------|
| id | TEXT PRIMARY KEY | UUID opportunity identifier |
| detected_at | TIMESTAMP | When opportunity was found |
| asset | TEXT | Asset symbol |
| settlement_time | TIMESTAMP | Market settlement time |
| threshold_ticker | TEXT | Threshold market ticker |
| threshold_strike | REAL | Strike price of threshold |
| threshold_yes_price | REAL | YES price of threshold |
| implied_price | REAL | Price implied by brackets |
| divergence | REAL | Threshold vs implied difference |
| net_profit_pct | REAL | Net profit percentage |
| max_liquidity_usd | REAL | Maximum trade size in USD |
| bracket_count | INTEGER | Number of brackets |
| was_traded | INTEGER | 0 = not traded, 1 = traded |
| trade_id | TEXT | Associated trade ID if traded |
| trade_mode | TEXT | 'paper' or 'live' if traded |

### manual_orders

| Field | Type | Description |
|-------|------|-------------|
| id | TEXT PRIMARY KEY | UUID order identifier |
| created_at | TIMESTAMP | Order creation time |
| ticker | TEXT | Kalshi market ticker |
| side | TEXT | 'yes' or 'no' position side |
| action | TEXT | 'buy' or 'sell' order action |
| count | INTEGER | Number of contracts (> 0) |
| price_cents | INTEGER | Order price in cents (1-99) |
| mode | TEXT | 'paper' or 'live' execution mode |
| status | TEXT | Order status (pending, filled, failed) |
| filled_count | INTEGER | Number of contracts filled |
| avg_fill_price | REAL | Average fill price in dollars |
| total_cost | REAL | Total cost in dollars |
| total_fees | REAL | Total fees paid |
| kalshi_order_id | TEXT | Kalshi API order ID (live only) |
| error | TEXT | Error message if failed |
| updated_at | TIMESTAMP | Last update time |

### watchlist

| Field | Type | Description |
|-------|------|-------------|
| id | TEXT PRIMARY KEY | UUID watchlist item identifier |
| ticker | TEXT | Kalshi market ticker (unique) |
| title | TEXT | Market title |
| subtitle | TEXT | Market subtitle/description |
| notes | TEXT | Optional user notes |
| added_at | TIMESTAMP | When added to watchlist |

### trading_signals

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing signal ID |
| ticker | TEXT | Kalshi market ticker |
| signal_type | TEXT | Signal type: 'buy_yes', 'buy_no', 'sell_yes', 'sell_no' |
| edge_percent | REAL | Edge percentage (e.g., 15.5 = 15.5% edge) |
| model_prob | REAL | Model's probability estimate (0.0-1.0) |
| market_price | INTEGER | Current market price in cents |
| recommended_size | INTEGER | Suggested position size |
| source | TEXT | Signal source: 'btc_price_model', 'manual', etc. |
| status | TEXT | Signal status: 'pending', 'executed', 'expired', 'rejected' |
| created_at | TIMESTAMP | When signal was generated |
| executed_at | TIMESTAMP | When signal was executed (if applicable) |
| execution_price | INTEGER | Actual execution price in cents (if executed) |
| notes | TEXT | Additional signal notes and context |

### auto_trader_config

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Always 1, single row table |
| enabled | INTEGER | Trading mode: 0=disabled, 1=paper only, 2=live enabled |
| min_edge_percent | REAL | Minimum edge required to trade |
| max_position_size | INTEGER | Maximum contracts per market |
| max_daily_loss_cents | INTEGER | Maximum daily loss limit in cents |
| max_open_positions | INTEGER | Maximum number of open positions |
| allowed_series | TEXT | Comma-separated series tickers to trade |
| updated_at | TIMESTAMP | Last configuration update |

### daily_pnl

| Field | Type | Description |
|-------|------|-------------|
| date | TEXT PRIMARY KEY | Trading date in YYYY-MM-DD format |
| realized_pnl_cents | INTEGER | Realized P&L for the day in cents |
| trades_count | INTEGER | Number of trades executed |
| updated_at | TIMESTAMP | Last update timestamp |

### btc_arb_executions

| Field | Type | Description |
|-------|------|-------------|
| id | TEXT PRIMARY KEY | UUID execution identifier |
| opportunity_id | TEXT | Associated opportunity UUID |
| executed_at | TIMESTAMP | Execution timestamp |
| mode | TEXT | Execution mode: 'paper' or 'live' |
| contracts_per_leg | INTEGER | Number of contracts per arbitrage leg |
| total_cost_cents | INTEGER | Total cost in cents |
| total_fees_cents | INTEGER | Total Kalshi fees in cents |
| guaranteed_profit_cents | INTEGER | Guaranteed profit amount in cents |
| status | TEXT | Execution status: 'open', 'settled', 'partial' |
| kalshi_response | TEXT | JSON response from Kalshi batch order |
| settled_at | TIMESTAMP | When arbitrage settled |
| settlement_outcome | TEXT | Settlement result description |
| actual_payout_cents | INTEGER | Actual payout received |
| actual_profit_cents | INTEGER | Actual profit after settlement |
| audit_id | TEXT | Execution audit trail ID (added in migration 001) |

### btc_arb_config

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Always 1, single row configuration table |
| min_edge_percent | REAL | Minimum edge percentage required to execute |
| default_budget_cents | INTEGER | Default budget per opportunity in cents |
| auto_trade_enabled | INTEGER | Auto-execution mode: 0=disabled, 1=enabled |
| scan_interval_seconds | REAL | Scanning frequency (default 2.0 seconds) |
| max_position_per_opp_cents | INTEGER | Maximum position size per opportunity |
| mode | TEXT | Trading mode: 'paper' or 'live' |
| updated_at | TIMESTAMP | Last configuration update |

### execution_audit

| Field | Type | Description |
|-------|------|-------------|
| id | TEXT PRIMARY KEY | UUID execution audit identifier |
| request_id | TEXT UNIQUE | UUID request identifier |
| created_at | TIMESTAMP | Execution timestamp (default: CURRENT_TIMESTAMP) |
| source | TEXT | Request source: 'orchestrator', 'manual', 'auto_trader', 'btc_arb', 'strategy' |
| signal_id | TEXT | Associated trading signal ID (optional) |
| mode | TEXT | Execution mode: 'paper', 'live', 'dual' |
| legs_json | TEXT | JSON array of execution legs |
| atomic | INTEGER | Atomic execution flag (default: 1) |
| max_slippage_cents | INTEGER | Maximum allowed slippage in cents |
| success | INTEGER | Overall execution success flag |
| total_cost_cents | INTEGER | Total cost across all legs |
| total_fees_cents | INTEGER | Total fees across all legs |
| execution_time_ms | INTEGER | Execution duration in milliseconds |
| leg_results_json | TEXT | JSON array of leg execution results |
| error | TEXT | Error message if execution failed |

### circuit_breaker_state (Updated Schema)

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Always 1, single row table |
| tripped | INTEGER | Circuit breaker status: 0=active, 1=tripped (default: 0) |
| trip_reason | TEXT | Reason for circuit breaker trip |
| trip_time | TIMESTAMP | When circuit breaker was tripped |
| permanent | INTEGER | Permanent trip flag: 0=temporary, 1=permanent (default: 0) |
| consecutive_losses | INTEGER | Count of consecutive losses (default: 0) |
| daily_loss_cents | INTEGER | Daily loss amount in cents (default: 0) |
| hourly_trades_json | TEXT | JSON tracking hourly trade counts |
| hourly_exposure_json | TEXT | JSON tracking hourly exposure limits |
| last_reset_date | TEXT | Date of last daily reset |
| updated_at | TIMESTAMP | Last update timestamp (default: CURRENT_TIMESTAMP) |

---

## Backend Request Models

### ExecuteRequest (backend/models/schemas.py)

| Field | Type | Description |
|-------|------|-------------|
| opportunity_id | str | UUID of opportunity to execute |
| num_contracts | int | Number of contract sets to buy |

### ResetRequest (backend/models/schemas.py)

| Field | Type | Description |
|-------|------|-------------|
| starting_balance | Optional[float] | New starting balance, defaults to config |

### TradeRequest (backend/models/schemas.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Kalshi market ticker |
| side | str | 'yes' or 'no' position side |
| action | str | 'buy' or 'sell' order action |
| count | int | Number of contracts to trade |
| price_cents | int | Order price in cents (1-99) |
| modes | List[str] | Execution modes: ['paper'], ['live'], or both |

### WatchlistAddRequest (backend/models/schemas.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Kalshi market ticker to add |
| notes | Optional[str] | Optional user notes about the market |

### ExecutionLeg (backend/models/execution_models.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Kalshi market ticker |
| side | 'yes' \| 'no' | Position side |
| action | 'buy' \| 'sell' | Order action |
| contracts | int | Number of contracts (must be positive) |
| price_cents | int | Price in cents (1-99) |
| price_type | 'limit' \| 'market' | Order price type (default: limit) |

### ExecutionRequest (backend/models/execution_models.py)

| Field | Type | Description |
|-------|------|-------------|
| request_id | str | UUID request identifier (auto-generated) |
| source | 'orchestrator' \| 'manual' \| 'auto_trader' \| 'btc_arb' \| 'strategy' | Request source |
| signal_id | Optional[str] | Associated trading signal ID |
| mode | 'paper' \| 'live' \| 'dual' | Execution mode |
| legs | List[ExecutionLeg] | Trade legs to execute (minimum 1) |
| atomic | bool | Whether all legs must succeed (default: True) |
| max_slippage_cents | int | Maximum allowed slippage in cents (default: 2) |
| timeout_seconds | float | Request timeout in seconds (default: 30.0) |

### LegResult (backend/models/execution_models.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market ticker |
| side | 'yes' \| 'no' | Position side |
| action | 'buy' \| 'sell' | Order action |
| requested_contracts | int | Contracts requested |
| filled_contracts | int | Contracts filled |
| requested_price_cents | int | Price requested in cents |
| fill_price_cents | Optional[int] | Actual fill price in cents |
| fee_cents | int | Fees charged (default: 0) |
| status | 'filled' \| 'partial' \| 'failed' \| 'cancelled' | Execution status |
| order_id | Optional[str] | Kalshi order ID |
| error | Optional[str] | Error message if failed |
| slippage_cents | int | Price slippage in cents (default: 0) |

### ExecutionResult (backend/models/execution_models.py)

| Field | Type | Description |
|-------|------|-------------|
| request_id | str | UUID request identifier |
| success | bool | Overall execution success |
| mode | 'paper' \| 'live' \| 'dual' | Execution mode |
| legs | List[LegResult] | Results for each leg |
| total_cost_cents | int | Total cost across all legs |
| total_fees_cents | int | Total fees across all legs |
| execution_time_ms | int | Execution duration in milliseconds |
| audit_id | str | Execution audit trail ID |
| created_at | datetime | Result creation timestamp (auto-generated) |
| error | Optional[str] | Error message if failed |

### PositionConfig (backend/services/core/position_manager.py)

| Field | Type | Description |
|-------|------|-------------|
| cache_ttl_seconds | int | How long to cache live positions (default: 30) |
| max_cache_entries | int | Maximum positions to cache (default: 500) |
| enable_caching | bool | Whether to cache live positions (default: True) |
| auto_refresh | bool | Auto-refresh expired cache on access (default: True) |

### UnifiedPosition (backend/services/core/position_manager.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market ticker (e.g., "KXBTC-24DEC31-100000") |
| side | str | Position side ("yes" or "no") |
| contracts | int | Number of contracts held (always positive) |
| avg_price_cents | int | Average entry price in cents |
| total_cost_cents | int | Total cost basis in cents |
| total_fees_cents | int | Total fees paid in cents (default: 0) |
| unrealized_pnl_cents | int | Unrealized P&L in cents (default: 0) |
| source | PositionSource | Source: PAPER, LIVE, or BOTH |
| created_at | Optional[datetime] | When position was opened |
| market_exposure_cents | int | Current market exposure (default: 0) |
| settlement_time | Optional[datetime] | Market settlement time |
| metadata | Dict[str, Any] | Additional source-specific data |

### ExposureSummary (backend/services/core/position_manager.py)

| Field | Type | Description |
|-------|------|-------------|
| total_exposure_cents | int | Total value at risk |
| position_count | int | Number of open positions |
| total_cost_cents | int | Sum of all position costs |
| total_fees_cents | int | Sum of all fees paid |
| by_side | Dict[str, int] | Breakdown by yes/no side |
| by_ticker | Dict[str, int] | Breakdown by market ticker |

---

## Data Models

### Market (backend/models/kalshi_models.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market identifier (e.g., "KXHIGHNY-24DEC31-62-63") |
| event_ticker | str | Event identifier |
| title | str | Market title text |
| status | MarketStatus | Market status (OPEN, CLOSED, SETTLED, etc.) |
| yes_bid | Optional[int] | Best YES bid price in cents (1-99) |
| yes_ask | Optional[int] | Best YES ask price in cents |
| no_bid | Optional[int] | Best NO bid price in cents |
| no_ask | Optional[int] | Best NO ask price in cents |
| floor_strike | Optional[int] | Lower temperature bound (integer degrees F) |
| cap_strike | Optional[int] | Upper temperature bound (integer degrees F) |
| volume_24h | int | 24-hour trading volume |
| open_interest | int | Total open contracts |
| close_time | Optional[datetime] | Market settlement time (UTC) |
| fetched_at | datetime | When market data was retrieved |

### Orderbook (backend/models/kalshi_models.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market identifier |
| yes_bids | List[OrderbookLevelModel] | YES bid levels |
| no_bids | List[OrderbookLevelModel] | NO bid levels |
| sequence | int | Orderbook sequence number |
| timestamp | datetime | Orderbook timestamp |

### Event (backend/models/kalshi_models.py)

| Field | Type | Description |
|-------|------|-------------|
| event_ticker | str | Event identifier |
| series_ticker | str | Series identifier |
| title | str | Event title |
| mutually_exclusive | bool | Whether exactly one market can win |
| markets | List[Market] | All markets in this event |

### Position (backend/models/kalshi_models.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market ticker |
| position | int | Positive for YES, negative for NO |
| total_cost_cents | int | Total cost paid |
| avg_cost_cents | float | Average cost per contract |
| realized_pnl_cents | int | Realized profit/loss |
| fees_paid_cents | int | Total fees paid |

### Order (backend/models/kalshi_models.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market ticker |
| side | OrderSide | YES or NO |
| action | OrderAction | BUY or SELL |
| count | int | Number of contracts |
| price_cents | int | Order price in cents (1-99) |
| status | Optional[str] | Order status |

### NWSForecast (backend/models/nws_models.py)

| Field | Type | Description |
|-------|------|-------------|
| city | str | City name |
| station_id | str | NWS station ID (e.g., "KNYC") |
| grid_id | str | Weather forecast office code |
| grid_x | int | Grid X coordinate |
| grid_y | int | Grid Y coordinate |
| forecast_high | int | Predicted high temperature (F) |
| forecast_low | int | Predicted low temperature (F) |
| weather_pattern | WeatherPattern | STABLE, TRANSITIONAL, STORMY, FRONTAL |
| confidence_level | float | Forecast confidence (0.0-1.0) |
| hourly_forecasts | List[HourlyForecast] | Hourly temperature data |
| generated_at | datetime | When forecast was issued |
| fetched_at | datetime | When forecast was retrieved |

### LocationConfig (backend/models/nws_models.py)

| Field | Type | Description |
|-------|------|-------------|
| city | str | City name |
| series_ticker | str | Kalshi series (e.g., "KXHIGHNY") |
| station_id | str | NWS station identifier |
| wfo | str | Weather forecast office |
| grid_x | int | NWS grid X coordinate |
| grid_y | int | NWS grid Y coordinate |
| latitude | float | Location latitude |
| longitude | float | Location longitude |
| timezone | str | Timezone string (e.g., "America/New_York") |
| typical_std_dev | float | Historical forecast standard deviation |
| settlement_hour | int | Hour when CLI data is generated (23) |

---

## Service Data Classes

### SpotPrice (backend/services/spot_price_client.py)

| Field | Type | Description |
|-------|------|-------------|
| asset | str | Asset symbol (e.g., "BTC") |
| price | float | Current spot price in USD |
| timestamp | datetime | Price fetch timestamp |
| source | str | API source ("CoinGecko", "CoinLore", or "unknown") |

### ThresholdMarket (backend/services/market_classifier.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Kalshi market ticker |
| title | str | Market title text |
| asset | str | Asset symbol |
| strike | float | Price threshold (e.g., 100000) |
| direction | str | "above" for > strike |
| yes_price | float | YES contract price 0.0-1.0 |
| yes_ask | float | Best YES ask price |
| volume | int | 24h trading volume |
| settlement_time | datetime | Market settlement time |

### BracketMarket (backend/services/market_classifier.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Kalshi market ticker |
| title | str | Market title text |
| asset | str | Asset symbol |
| low_bound | float | Lower price boundary |
| high_bound | float | Upper price boundary |
| yes_price | float | YES contract price 0.0-1.0 |
| yes_ask | float | Best YES ask price |
| volume | int | 24h trading volume |
| settlement_time | datetime | Market settlement time |

### MarketGroup (backend/services/market_classifier.py)

| Field | Type | Description |
|-------|------|-------------|
| asset | str | Asset symbol |
| settlement_time | datetime | Common settlement time |
| thresholds | List[ThresholdMarket] | Threshold markets in group |
| brackets | List[BracketMarket] | Bracket markets in group |
| spot_price | Optional[float] | Current spot price |

### ArbitrageOpportunity (backend/services/arbitrage_detector.py)

| Field | Type | Description |
|-------|------|-------------|
| id | str | UUID identifier |
| asset | str | Asset symbol |
| detected_at | datetime | Detection timestamp |
| settlement_time | datetime | Market settlement time |
| threshold | ThresholdMarket | Threshold market data |
| brackets | List[BracketMarket] | All brackets to buy |
| threshold_yes_price | float | Threshold YES price |
| implied_price | float | Sum of brackets above strike |
| divergence | float | Threshold vs implied difference |
| cost_per_set | float | Cost for one complete set |
| fees_per_set | float | Fees for one complete set |
| profit_per_set | float | Net profit per set |
| net_profit_pct | float | Profit as percentage |
| max_contracts | int | Max contracts from liquidity |
| max_liquidity_usd | float | Max trade size in USD |
| spot_price | Optional[float] | Current spot price |

### OrderLeg (backend/services/fee_calculator.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market ticker |
| side | str | 'yes' or 'no' |
| contracts | int | Number of contracts |
| price | float | Contract price 0.0-1.0 |

### PaperOrderResult (backend/services/paper_trading.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market ticker |
| side | str | 'yes' or 'no' |
| contracts | int | Contracts filled |
| fill_price | float | Execution price |
| fee | float | Fee charged |
| status | str | Always "filled" for paper |

### PaperTradeResult (backend/services/paper_trading.py)

| Field | Type | Description |
|-------|------|-------------|
| trade_id | str | UUID trade identifier |
| status | str | 'success' or 'failed' |
| orders | List[PaperOrderResult] | All executed orders |
| total_cost | float | Sum of order costs |
| total_fees | float | Sum of order fees |
| expected_payout | float | Guaranteed $1 per set |
| expected_profit | float | Payout minus costs |
| expected_profit_pct | float | Profit percentage |
| message | str | Status message |
| paper_mode | bool | Always True |

### LiveTradeResult (backend/services/trade_executor.py)

| Field | Type | Description |
|-------|------|-------------|
| trade_id | str | UUID trade identifier |
| status | str | 'success' or 'partial' |
| orders | list | Kalshi order responses |
| total_cost | float | Sum of order costs |
| total_fees | float | Sum of order fees |
| expected_payout | float | Expected payout |
| expected_profit | float | Expected profit |
| message | str | Status message |
| paper_mode | bool | Always False |

### ArbLeg (backend/services/btc_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Kalshi market ticker |
| market_type | str | Market type: 'range' or 'threshold' |
| side | str | Position side: 'yes' or 'no' |
| action | str | Order action: 'buy' |
| price_cents | int | Order price in cents |
| strike | Optional[float] | Strike price for threshold markets |
| lower_bound | Optional[float] | Lower bound for range markets |
| upper_bound | Optional[float] | Upper bound for range markets |

### ArbOpportunity (backend/services/btc_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| id | str | UUID opportunity identifier |
| event_date | str | Settlement event date (e.g., '25DEC3119') |
| settlement_time | str | ISO settlement timestamp |
| legs | List[ArbLeg] | All three arbitrage legs |
| total_cost_cents | int | Total cost for one contract set |
| guaranteed_payout_cents | int | Always 100 (cents) |
| edge_cents | int | Guaranteed profit in cents |
| edge_percent | float | Profit percentage |
| detected_at | str | ISO detection timestamp |
| range_description | str | Human-readable range (e.g., "$87,500 - $87,749.99") |

### EngineConfig (backend/services/btc_arb_engine.py)

| Field | Type | Description |
|-------|------|-------------|
| min_edge_percent | float | Minimum edge required (default 3.0) |
| budget_cents | int | Budget per opportunity (default 10000) |
| auto_trade_enabled | bool | Auto-execution enabled flag |
| mode | str | Trading mode: 'paper' or 'live' |
| scan_interval_seconds | float | Scan frequency (default 2.0) |
| max_position_per_opp_cents | int | Max position size (default 50000) |

### EngineStatus (backend/services/btc_arb_engine.py)

| Field | Type | Description |
|-------|------|-------------|
| is_running | bool | Engine running state |
| last_scan_at | str \| null | ISO timestamp of last scan |
| last_scan_duration_ms | int | Last scan duration in milliseconds |
| total_scans | int | Total number of scans performed |
| opportunities_found | int | Opportunities in current scan |
| auto_executions | int | Total auto-executions performed |
| last_error | str \| null | Last error message if any |
| all_calculations | List[CalculationResult] | All calculations sorted by cost |
| near_misses | List[CalculationResult] | Calculations with cost 100-105¢ |
| profitable | List[CalculationResult] | Calculations with cost < 100¢ |
| market_data | Dict | Range/threshold market data and event dates |
| activity_log | List[LogEntry] | Recent activity log messages |

### CalculationResult (backend/services/btc_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| range_ticker | str | Range market ticker |
| range_description | str | Human-readable range description |
| lower_bound | float | Range lower boundary |
| upper_bound | float | Range upper boundary |
| range_yes_ask | int \| null | Range YES ask price in cents |
| lower_thresh_ticker | str \| null | Lower threshold market ticker |
| lower_thresh_no_cost | int \| null | Lower threshold NO cost in cents |
| upper_thresh_ticker | str \| null | Upper threshold market ticker |
| upper_thresh_yes_ask | int \| null | Upper threshold YES ask price |
| total_cost_cents | int \| null | Total arbitrage cost in cents |
| edge_cents | int \| null | Arbitrage edge in cents |
| is_profitable | bool | Whether opportunity is profitable |
| reason | str | Reason for profitability/failure |
| event_date | str | Event date identifier |

### SimplifiedMarket (backend/services/btc_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market ticker |
| market_type | str | Market type: 'range' or 'threshold' |
| yes_ask | int \| null | YES ask price in cents |
| yes_bid | int \| null | YES bid price in cents |
| no_ask | int \| null | NO ask price in cents |
| no_bid | int \| null | NO bid price in cents |
| description | str | Human-readable market description |
| event_date | str | Event date identifier |

### ScanResult (backend/services/btc_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| opportunities | List[ArbOpportunity] | Found arbitrage opportunities |
| range_markets | List[SimplifiedMarket] | Simplified range market data |
| threshold_markets | List[SimplifiedMarket] | Simplified threshold market data |
| calculations | List[CalculationResult] | All arbitrage calculations performed |
| stats | Dict | Scan statistics and metrics |
| timestamp | str | ISO timestamp of scan completion |

### ReconciliationConfig (backend/services/reconciliation/reconciler.py)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| run_interval_seconds | int | 300 | Interval between automatic reconciliation runs |
| critical_threshold_cents | int | 1000 | Threshold for critical discrepancies |
| critical_threshold_contracts | int | 10 | Contract threshold for critical discrepancies |
| halt_on_critical | bool | True | Whether to halt trading on critical discrepancies |
| auto_start | bool | False | Whether to start reconciliation automatically |

### Discrepancy (backend/services/reconciliation/reconciler.py)

| Field | Type | Description |
|-------|------|-------------|
| type | DiscrepancyType | Type of discrepancy found |
| severity | Severity | Severity level (info, warning, critical) |
| ticker | str | Market ticker affected |
| local_data | Optional[dict] | Local position/balance data |
| remote_data | Optional[dict] | Kalshi API data |
| details | dict | Additional context about the discrepancy |

### TradingSignal (backend/services/core/base_strategy.py)

| Field | Type | Description |
|-------|------|-------------|
| id | str | Unique signal identifier |
| strategy_type | StrategyType | Strategy that generated this signal |
| ticker | str | Primary market ticker |
| signal_type | SignalType | Type of signal (DIRECTIONAL, ARBITRAGE, SPREAD) |
| edge_percent | float | Calculated edge percentage |
| model_prob | float | Model probability estimate |
| market_price | float | Current market price |
| recommended_size | int | Recommended position size in contracts |
| confidence | float | Signal confidence score 0.0-1.0 |
| is_arbitrage | bool | True if this is an arbitrage opportunity |
| legs | List[SignalLeg] | Individual trade legs for multi-leg signals |
| status | SignalStatus | Current signal status |
| created_at | datetime | Signal generation timestamp |
| expires_at | datetime | Signal expiration timestamp |
| notes | Optional[str] | Additional notes or context |

### SignalLeg (backend/services/core/base_strategy.py)

| Field | Type | Description |
|-------|------|-------------|
| ticker | str | Market ticker for this leg |
| side | str | 'yes' or 'no' side |
| action | str | 'buy' or 'sell' action |
| price_cents | int | Target price in cents |
| strike | Optional[int] | Strike price for threshold markets |
| bounds | Optional[tuple] | (floor, cap) for bracket markets |
| description | str | Human-readable description of this leg |

---

## Frontend Hook Types (frontend/src/hooks/useSpotPrice.ts)

### SpotPriceData

| Field | Type | Description |
|-------|------|-------------|
| price | number | Current spot price in USD |
| source | string | API source ("CoinGecko", "CoinLore") |
| timestamp | string | ISO timestamp of price fetch |
| isLive | boolean | True if data is fresh (<60s old) |

### UseSpotPriceResult

| Field | Type | Description |
|-------|------|-------------|
| data | SpotPriceData \| null | Current price data or null |
| error | string \| null | Error message if fetch failed |
| isLoading | boolean | True during initial fetch |
| refresh | () => void | Manual refresh function |

---

## Frontend Types (frontend/src/types/index.ts)

### TradingMode

| Value | Description |
|-------|-------------|
| 'paper' | Simulated trading mode |
| 'live' | Real money trading mode |

### Bracket

| Field | Type | Description |
|-------|------|-------------|
| ticker | string | Market ticker |
| low | number | Lower price bound |
| high | number | Upper price bound |
| yes_price | number | YES contract price |

### Opportunity

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID identifier |
| asset | string | Asset symbol |
| settlement_time | string | ISO settlement time |
| threshold_ticker | string | Threshold market ticker |
| threshold_title | string | Market title |
| threshold_strike | number | Strike price |
| bracket_count | number | Number of brackets |
| cost_per_set | number | Cost per contract set |
| fees_per_set | number | Fees per contract set |
| profit_per_set | number | Profit per contract set |
| net_profit_pct | number | Profit percentage |
| max_contracts | number | Maximum contracts |
| max_liquidity_usd | number | Max trade size USD |
| spot_price | number \| null | Current spot price |
| brackets | Bracket[] | All bracket markets |

### Balance

| Field | Type | Description |
|-------|------|-------------|
| available_balance | number | Spendable balance |
| starting_balance | number | Balance at reset (paper) |
| paper_mode | boolean | True if paper trading |

### Position

| Field | Type | Description |
|-------|------|-------------|
| id | string | Position UUID |
| ticker | string | Market ticker |
| side | string | 'yes' or 'no' |
| contracts | number | Number held |
| avg_price | number | Average entry price |
| total_cost | number | Total cost paid |
| total_fees | number | Fees paid |
| settlement_time | string | ISO settlement time |
| settled | number | 0 = open, 1 = settled |
| realized_pnl | number | Realized P&L if settled |

### Trade

| Field | Type | Description |
|-------|------|-------------|
| id | string | Trade UUID |
| executed_at | string | ISO execution time |
| asset | string | Asset symbol |
| total_cost | number | Total cost |
| total_fees | number | Total fees |
| expected_payout | number | Expected payout |
| expected_profit | number | Expected profit |
| expected_profit_pct | number | Profit percentage |
| status | string | Trade status |

### PnLSummary

| Field | Type | Description |
|-------|------|-------------|
| current_balance | number | Current balance |
| starting_balance | number | Starting balance |
| total_pnl | number | Total P&L dollars |
| total_pnl_pct | number | Total P&L percentage |
| realized_pnl | number | Realized P&L |
| open_positions_value | number | Value in open positions |
| total_trades | number | Number of trades |

### TradeResult

| Field | Type | Description |
|-------|------|-------------|
| trade_id | string | Trade UUID |
| status | string | 'success' or 'error' |
| total_cost | number | Total cost |
| total_fees | number | Total fees |
| expected_payout | number | Expected payout |
| expected_profit | number | Expected profit |
| message | string | Status message |
| paper_mode | boolean | True if paper trade |
| orders | Array<{ticker, contracts, price, fee}> | Order details |

---

## Arbitrage Hub Types (frontend/src/components/arbitrage/)

### CryptoAsset (CryptoArbitrageSection.tsx)

| Field | Type | Description |
|-------|------|-------------|
| id | string | Asset identifier (BTC, ETH, SOL, XRP) |
| name | string | Full asset name (Bitcoin, Ethereum, etc.) |
| code | string | Market code |
| icon | string | Unicode icon (₿, Ξ, ◎, ✕) |
| series | string | Range market series (KXBTC, KXETH) |
| thresholdSeries | string | Threshold market series (KXBTCD, KXETHD) |
| enabled | boolean | Whether scanner is active |
| color | string | Tailwind gradient classes |
| borderColor | string | Tailwind border color classes |

### StatItem (shared/StatsBar.tsx)

| Field | Type | Description |
|-------|------|-------------|
| value | number \| string | Stat value to display |
| label | string | Stat label |
| color | string | Tailwind text color class |

### ViewMode (CryptoArbitrageSection.tsx)

| Value | Description |
|-------|-------------|
| 'overview' | Card grid view showing all cryptos |
| 'scanner' | Detailed scanner view for specific crypto |

### TableColumn (shared/OpportunityTable.tsx)

| Field | Type | Description |
|-------|------|-------------|
| key | string | Column identifier |
| label | string | Column header text |
| align | 'left' \| 'right' \| 'center' | Text alignment |
| bold | boolean | Whether header should be bold |

---

## Weather Types (frontend/src/types/weather.ts)

### BracketMarket

| Field | Type | Description |
|-------|------|-------------|
| ticker | string | Kalshi market ticker |
| title | string | Market title text |
| floor_strike | number \| null | Lower temperature bound (null for ≤X brackets) |
| cap_strike | number \| null | Upper temperature bound (null for ≥X brackets) |
| yes_ask | number | YES ask price in cents |
| yes_bid | number | YES bid price in cents |
| no_ask | number | NO ask price in cents |
| no_bid | number | NO bid price in cents |
| volume | number | Trading volume |

### BracketTotals

| Field | Type | Description |
|-------|------|-------------|
| yes_ask | number | Sum of all YES ask prices in series |
| yes_bid | number | Sum of all YES bid prices in series |
| no_ask | number | Sum of all NO ask prices in series |
| no_bid | number | Sum of all NO bid prices in series |
| volume | number | Sum of all volumes in series |

### ArbitrageStrategy

| Field | Type | Description |
|-------|------|-------------|
| cost | number | Total cost to execute strategy in cents |
| payout | number | Guaranteed payout amount in cents |
| profit | number | Net profit (payout - cost) in cents |
| is_arb | boolean | Whether strategy is profitable (cost < payout) |
| brackets | Array<{title: string, no_ask: number}> \| undefined | Bracket details for min_2_no strategy |

### ArbitrageAnalysis

| Field | Type | Description |
|-------|------|-------------|
| all_yes | ArbitrageStrategy | Buy YES on every bracket (arb if sum < 100¢) |
| all_no | ArbitrageStrategy | Buy NO on every bracket (arb if sum < (n-1)*100¢) |
| min_2_no | ArbitrageStrategy | Buy 2 cheapest NOs (arb if sum < 100¢) |
| best_strategy | string \| null | Name of best strategy ('all_yes', 'all_no', 'min_2_no') |
| has_arbitrage | boolean | Whether any strategy is profitable |

### SeriesResult

| Field | Type | Description |
|-------|------|-------------|
| series | string | Series ticker (e.g., KXHIGHNY) |
| market_type | 'high' \| 'low' | Temperature market type |
| bracket_count | number | Number of brackets in series |
| brackets | BracketMarket[] | All brackets for this series |
| best_cost | number \| null | Total cost to buy all YES positions |
| totals | BracketTotals \| null | Sums of all ask/bid prices and volume |
| arbitrage | ArbitrageAnalysis \| null | Three-strategy arbitrage analysis |
| opportunities | WeatherOpportunity[] | Found arbitrage opportunities |
| near_misses | NearMissRecord[] | Near-miss opportunities |
| forecast | SeriesForecast \| null | NWS forecast data |
| error | string \| null | Error message if scan failed |

### CityResult

| Field | Type | Description |
|-------|------|-------------|
| code | string | City code (NYC, LAX, etc.) |
| city | string | City name |
| high | SeriesResult \| null | HIGH temperature series data |
| low | SeriesResult \| null | LOW temperature series data |

### WeatherStatus

| Field | Type | Description |
|-------|------|-------------|
| running | boolean | Scanner running state |
| scan_count | number | Total scans performed |
| last_scan | string \| null | ISO timestamp of last scan |
| cities | Record<string, CityResult> | All city results by code |
| opportunities | WeatherOpportunity[] | All found opportunities |
| near_misses | NearMissRecord[] | All near-miss records |
| forecasts | Record<string, ForecastData> | NWS forecasts by city code |
| stats | object | Summary statistics |

---

## Diagnostic and Testing Types

### DiagnosticResult (diagnose_infrastructure.py)

| Field | Type | Description |
|-------|------|-------------|
| component | str | Component name being tested |
| status | 'passed' \| 'failed' \| 'warning' | Test result status |
| message | str | Human-readable result message |
| details | Optional[str] | Additional error details or context |
| error | Optional[Exception] | Exception object if test failed |

### SystemStatus (diagnose_infrastructure.py)

| Field | Type | Description |
|-------|------|-------------|
| database | bool | Database connectivity and schema status |
| imports | bool | Component import success status |
| instantiation | bool | Component creation success status |
| tests | bool | Core test suite execution status |
| overall | bool | Overall system health status |
| timestamp | str | ISO timestamp of diagnostic run |
| issues | List[str] | List of identified issues |
| fixes_applied | List[str] | List of fixes that were applied |

### TestResults (test1.py)

| Field | Type | Description |
|-------|------|-------------|
| passed | int | Number of tests that passed |
| failed | int | Number of tests that failed |
| warnings | int | Number of warnings generated |
| total | int | Total number of tests run |
| success_rate | float | Percentage of tests that passed |
| execution_time | float | Total test execution time in seconds |

### ComponentTestStatus (test1.py)

| Field | Type | Description |
|-------|------|-------------|
| module | str | Module name being tested |
| class_name | str | Class name being tested |
| import_success | bool | Whether module imported successfully |
| instantiation_success | bool | Whether class could be instantiated |
| error | Optional[str] | Error message if test failed |
