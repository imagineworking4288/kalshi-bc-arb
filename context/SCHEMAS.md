# Data Schemas

## Configuration

### Settings (backend/config.py)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| kalshi_api_url | str | "https://api.elections.kalshi.com/trade-api/v2" | Kalshi production API endpoint (updated URL) |
| kalshi_api_key_id | str | "" | API key ID from Kalshi dashboard |
| kalshi_private_key_path | str | "./keys/kalshi-private-key.pem" | Path to RSA private key file |
| paper_trading_mode | bool | True | True for simulation, False for real money |
| paper_starting_balance | float | 10000.00 | Initial paper account balance |
| database_path | str | "./data/kalshi_arb.db" | SQLite database file path |
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
| volume | number | Trading volume |

### SeriesResult

| Field | Type | Description |
|-------|------|-------------|
| series | string | Series ticker (e.g., KXHIGHNY) |
| market_type | 'high' \| 'low' | Temperature market type |
| bracket_count | number | Number of brackets in series |
| brackets | BracketMarket[] | All brackets for this series |
| best_cost | number \| null | Total cost to buy all YES positions |
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
