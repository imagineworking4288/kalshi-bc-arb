# API Reference

## backend/

### main.py
FastAPI application entry point with lifespan management

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| lifespan | app: FastAPI | AsyncGenerator | Init database, print startup banner, handle shutdown |
| health | - | dict | Health check endpoint, returns status and paper mode |

### config.py
Application settings from environment variables

| Function/Property | Params | Returns | Description |
|----------|--------|---------|-------------|
| Settings | - | BaseSettings | Pydantic settings class with Kalshi/trading config |
| Settings.kalshi_ws_url | - | str | Property: derive WebSocket URL from API URL |
| Settings.has_kalshi_credentials | - | bool | Property: check if API key and private key exist |
| get_settings | - | Settings | Cached settings singleton via lru_cache |

---

## backend/api/

### routes.py
HTTP REST API endpoints for opportunities and trading

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| get_config | - | dict | Return paper_mode, api_configured, starting balance |
| get_spot_price | - | dict | Fetch BTC spot price from CF Benchmarks |
| get_opportunities | min_profit: float = 1.0 | dict | Fetch markets, classify, detect arbitrage opportunities |
| get_balance | - | dict | Get account balance (paper or live) |
| get_positions | - | dict | Get open positions with paper_mode flag |
| execute_arbitrage | request: ExecuteRequest | dict | Execute arbitrage trade by opportunity ID |
| reset_paper | request: ResetRequest | dict | Reset paper trading account to starting balance |
| paper_summary | - | dict | Get paper trading P&L summary |
| paper_trades | limit: int = 50 | dict | Get paper trade history |
| settle_position | position_id: str, won: bool | dict | Manually settle paper position for testing |

### websocket.py
WebSocket connection manager for real-time updates

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ConnectionManager | - | - | Manages active WebSocket connections |
| ConnectionManager.connect | websocket: WebSocket | None | Accept and register new connection |
| ConnectionManager.disconnect | websocket: WebSocket | None | Remove connection from active set |
| ConnectionManager.broadcast | message: dict | None | Send JSON message to all connections |
| websocket_endpoint | websocket: WebSocket | None | Handle WebSocket connection, respond to pings |

---

## backend/database/

### connection.py
Async SQLite database connection manager

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| Database | - | - | Database manager with path from settings |
| Database.initialize | - | None | Create database file and execute schema.sql |
| Database.connection | - | AsyncContextManager | Async context manager yielding aiosqlite connection |
| db | - | Database | Module-level Database singleton instance |

---

## backend/models/

### schemas.py
Pydantic request/response models

| Class | Fields | Description |
|-------|--------|-------------|
| ExecuteRequest | opportunity_id: str, num_contracts: int | Request body for execute arbitrage endpoint |
| ResetRequest | starting_balance: Optional[float] | Request body for paper account reset |

---

## backend/services/

### kalshi_client.py
HTTP client for Kalshi REST API

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| KalshiClient | - | - | Initialize with settings, create auth if credentials exist |
| KalshiClient._request | method, endpoint, params, json | dict | Make authenticated HTTP request to Kalshi API |
| KalshiClient.get_markets | limit: int | List[Dict] | Fetch markets from Kalshi (status filter removed) |
| KalshiClient.get_market | ticker: str | Dict | Get single market by ticker |
| KalshiClient.get_orderbook | ticker: str, depth: int | Dict | Get orderbook for market |
| KalshiClient.get_balance | - | Dict | Get account balance |
| KalshiClient.get_positions | status: str | List[Dict] | Get portfolio positions |
| KalshiClient.place_order | ticker, side, action, count, price, order_type | Dict | Place limit order on Kalshi |

### spot_price_client.py
BTC spot price from free APIs with fallback support

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| SpotPrice | asset, price, timestamp, source | dataclass | Spot price data with source attribution |
| SpotPriceClient | base_url: str = None | - | Client with CoinGecko/CoinLore endpoints and cache |
| SpotPriceClient.get_price | asset: str = "BTC" | Optional[SpotPrice] | Fetch price from CoinGecko with CoinLore fallback |
| SpotPriceClient._fetch_coingecko | asset: str | Optional[SpotPrice] | Primary: CoinGecko API (30 calls/min free) |
| SpotPriceClient._fetch_coinlore | asset: str | Optional[SpotPrice] | Fallback: CoinLore API (no published limits) |

### market_classifier.py
Classify Kalshi markets as threshold or bracket type

| Class/Enum | Values/Fields | Description |
|------------|---------------|-------------|
| MarketType | THRESHOLD, BRACKET | Enum for market classification |
| ThresholdMarket | ticker, title, asset, strike, direction, prices, volume, settlement | Threshold market data |
| BracketMarket | ticker, title, asset, low_bound, high_bound, prices, volume, settlement | Bracket market data |
| MarketGroup | asset, settlement_time, thresholds, brackets, spot_price | Group of related markets |

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| MarketClassifier.classify | market: dict | Tuple[MarketType, dict] | Parse market title, return type and extracted data |

### arbitrage_detector.py
Detect arbitrage opportunities between threshold and bracket markets

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ArbitrageOpportunity | id, asset, times, threshold, brackets, prices, costs, liquidity | dataclass | Complete arbitrage opportunity data |
| ArbitrageDetector | min_profit_pct, min_liquidity_usd | - | Detector with configurable thresholds |
| ArbitrageDetector.find_opportunities | groups: List[MarketGroup] | List[ArbitrageOpportunity] | Find all profitable arbitrage opportunities |
| ArbitrageDetector._analyze_threshold | threshold, brackets, group | Optional[ArbitrageOpportunity] | Analyze single threshold against brackets |

### fee_calculator.py
Kalshi trading fee calculations

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| OrderLeg | ticker, side, contracts, price | dataclass | Single order leg data |
| calculate_fee | contracts: int, price: float | float | Kalshi fee: ceil(0.07 * contracts * price * (1-price)) |
| calculate_arbitrage_cost | legs: List[OrderLeg] | dict | Total cost, fees, payout, profit for multi-leg trade |

### paper_trading.py
Simulated paper trading service

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PaperOrderResult | ticker, side, contracts, fill_price, fee, status | dataclass | Simulated order result |
| PaperTradeResult | trade_id, status, orders, costs, profit, message | dataclass | Complete paper trade result |
| PaperTradingService.get_balance | - | dict | Get paper account balance |
| PaperTradingService.reset_account | starting_balance: Optional[float] | dict | Reset to starting balance, clear positions |
| PaperTradingService.execute_arbitrage | opportunity, num_contracts | PaperTradeResult | Execute simulated arbitrage trade |
| PaperTradingService.get_positions | include_settled: bool | List[dict] | Get paper positions |
| PaperTradingService.get_trades | limit: int | List[dict] | Get paper trade history |
| PaperTradingService.get_pnl_summary | - | dict | Calculate P&L statistics |
| PaperTradingService.settle_position | position_id, won | dict | Manually settle position for testing |

### trade_executor.py
Route trades to paper simulation or live Kalshi

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| LiveTradeResult | trade_id, status, orders, costs, profit, message | dataclass | Live trade execution result |
| TradeExecutor | kalshi_client: KalshiClient | - | Initialize with Kalshi client and paper service |
| TradeExecutor.is_paper_mode | - | bool | Property: check if paper trading mode |
| TradeExecutor.get_balance | - | dict | Get balance from paper or Kalshi |
| TradeExecutor.get_positions | - | list | Get positions from paper or Kalshi |
| TradeExecutor.execute_arbitrage | opportunity, num_contracts | Union[Paper,Live]TradeResult | Route to paper or live execution |
| TradeExecutor._execute_live | opportunity, num_contracts | LiveTradeResult | Execute concurrent orders on Kalshi |

---

## backend/utils/

### kalshi_auth.py
RSA-PSS authentication for Kalshi API

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| KalshiAuth | api_key_id: str, private_key_path: str | - | Load RSA private key for signing |
| KalshiAuth._load_key | path: str | RSAPrivateKey | Read and parse PEM private key |
| KalshiAuth.get_headers | method: str, path: str | dict | Generate signed auth headers with timestamp |

---

## frontend/src/

### main.tsx
React application entry point

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| - | - | - | Render App in React.StrictMode to root element |

### App.tsx
Root application component with tab navigation

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| App | - | JSX.Element | Main app with Header, TabNav, tab content |

---

## frontend/src/services/

### api.ts
Backend HTTP API client

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| fetchJson | url: string, options?: RequestInit | Promise<T> | Fetch JSON with error handling |
| api.getConfig | - | Promise<{paper_mode, api_configured}> | Get backend configuration |
| api.getSpotPrice | - | Promise<{asset, price}> | Get current BTC spot price |
| api.getOpportunities | minProfit?: number | Promise<{opportunities, count}> | Get arbitrage opportunities |
| api.getBalance | - | Promise<Balance> | Get account balance |
| api.getPositions | - | Promise<{positions}> | Get open positions |
| api.executeArbitrage | opportunityId, numContracts | Promise<TradeResult> | Execute arbitrage trade |
| api.resetPaper | startingBalance?: number | Promise<any> | Reset paper account |
| api.getPaperSummary | - | Promise<PnLSummary> | Get paper P&L summary |
| api.getPaperTrades | limit?: number | Promise<{trades}> | Get paper trade history |

---

## frontend/src/stores/

### opportunityStore.ts
Zustand store for arbitrage opportunities

| Property/Function | Type | Description |
|----------|------|-------------|
| opportunities | Opportunity[] | List of detected opportunities |
| spotPrice | number \| null | Current BTC spot price |
| loading | boolean | Loading state flag |
| error | string \| null | Error message |
| setOpportunities | (opps) => void | Update opportunities list |
| setSpotPrice | (price) => void | Update spot price |
| setLoading | (loading) => void | Set loading state |
| setError | (error) => void | Set error message |

### tradingStore.ts
Zustand store for trading state

| Property/Function | Type | Description |
|----------|------|-------------|
| mode | TradingMode | Current mode: 'paper' or 'live' |
| balance | Balance \| null | Account balance info |
| positions | Position[] | Open positions list |
| selectedOpportunity | Opportunity \| null | Opportunity for execution modal |
| executeModalOpen | boolean | Modal visibility state |
| setMode | (mode) => void | Set trading mode |
| setBalance | (balance) => void | Update balance |
| setPositions | (positions) => void | Update positions |
| openExecuteModal | (opp) => void | Open modal with opportunity |
| closeExecuteModal | () => void | Close modal, clear selection |

---

## frontend/src/utils/

### format.ts
Formatting utility functions

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| formatCurrency | value: number | string | Format as USD with 2 decimals |
| formatPrice | value: number | string | Format as USD with 0 decimals |
| formatTimeRemaining | isoString: string | string | Format time until settlement |

---

## frontend/src/components/layout/

### Header.tsx
Application header with trading mode and balance

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| Header | - | JSX.Element | Display title, mode badge, BTC price, balance |

### TabNav.tsx
Tab navigation for main sections

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| TabNav | activeTab, onTabChange | JSX.Element | Render tab buttons for opportunities/trading/analytics |

---

## frontend/src/components/common/

### Modal.tsx
Reusable modal dialog component

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| Modal | children, onClose | JSX.Element | Overlay modal with backdrop click to close |

---

## frontend/src/components/opportunities/

### OpportunitiesTab.tsx
Main opportunities view with auto-refresh

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| OpportunitiesTab | - | JSX.Element | Fetch and display opportunities, 30s auto-refresh |

### OpportunityCard.tsx
Individual arbitrage opportunity display

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| OpportunityCard | opportunity: Opportunity | JSX.Element | Show opportunity details, profit %, execute button |

### ExecuteModal.tsx
Trade execution confirmation dialog

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ExecuteModal | - | JSX.Element | Contract input, cost preview, execute/cancel buttons |

---

## frontend/src/components/trading/

### TradingTab.tsx
Trading dashboard main view

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| TradingTab | - | JSX.Element | Show mode toggle, banner, balance, positions, history |

### ModeBanner.tsx
Paper/live mode status banner

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ModeBanner | - | JSX.Element | Show mode warning, reset button for paper |

### ModeToggle.tsx
Paper/live trading mode switcher

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ModeToggle | - | JSX.Element | Toggle buttons with live mode confirmation dialog |

### PositionList.tsx
Open positions display with auto-refresh

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PositionList | - | JSX.Element | List positions with ticker, contracts, cost |

### TradeHistory.tsx
Historical trades list for paper trading

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| TradeHistory | - | JSX.Element | List recent paper trades with profit |

---

## frontend/src/components/analytics/

### AnalyticsTab.tsx
Paper trading P&L analytics dashboard

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| AnalyticsTab | - | JSX.Element | Display P&L summary cards and details |

---

## Root Diagnostic Scripts

### diagnose_kalshi.py
Legacy Kalshi API diagnostic script

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| test_kalshi_auth | - | bool | Test authentication with old API endpoint |

### diagnose_kalshi_v2.py
Updated Kalshi API diagnostic with new endpoint

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| load_private_key | path: str | RSAPrivateKey | Load PEM private key from file |
| sign_request_pss | private_key, timestamp, method, path | str | RSA-PSS signature with DIGEST_LENGTH salt |
| test_kalshi_auth | - | bool | Test auth with new api.elections.kalshi.com endpoint |
| test_markets | - | bool | Test markets endpoint with authentication |
| test_btc_markets | - | bool | Search for BTC-related markets in response |

### start.bat
Windows batch script launcher

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| - | - | - | Start backend and frontend servers in separate terminals |
