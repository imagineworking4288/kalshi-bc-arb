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
