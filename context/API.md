# API Reference

## backend/

### main.py
FastAPI application entry point with lifespan management

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| lifespan | app: FastAPI | AsyncGenerator | Init database, auto-trader, BTC arbitrage engine, print startup banner, handle shutdown |
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
| get_spot_price | - | dict | Fetch BTC spot price from CoinGecko/CoinLore with source attribution |
| get_opportunities | min_profit: float = 1.0 | dict | Fetch events with nested markets, classify, detect arbitrage opportunities |
| get_balance | - | dict | Get account balance (paper or live) |
| get_positions | - | dict | Get open positions with paper_mode flag |
| execute_arbitrage | request: ExecuteRequest | dict | Execute arbitrage trade by opportunity ID |
| reset_paper | request: ResetRequest | dict | Reset paper trading account to starting balance |
| paper_summary | - | dict | Get paper trading P&L summary |
| paper_trades | limit: int = 50 | dict | Get paper trade history |
| settle_position | position_id: str, won: bool | dict | Manually settle paper position for testing |
| place_trade | request: TradeRequest | dict | Execute manual trade in paper/live/both modes |
| get_market_details | ticker: str | dict | Fetch market details from Kalshi API |
| get_portfolio_summary | - | dict | Get portfolio summary across paper and live modes |
| get_portfolio_positions | - | dict | Get all positions from paper and live modes |
| get_portfolio_orders | mode?: str, limit: int = 50 | dict | Get manual order history with optional mode filter |
| get_watchlist | - | dict | Get all watchlist items with fresh prices |
| add_to_watchlist | request: WatchlistAddRequest | dict | Add market to watchlist |
| remove_from_watchlist | ticker: str | dict | Remove market from watchlist |
| get_auto_trader_status | - | dict | Get current auto-trader status and configuration |
| update_auto_trader_config | request: dict | dict | Update auto-trader configuration parameters |
| start_auto_trader | - | dict | Start the auto-trader background process |
| stop_auto_trader | - | dict | Stop the auto-trader background process |
| manual_scan | - | dict | Manually trigger edge scan without executing trades |
| get_signals | status?: str, limit: int = 50 | dict | Get trading signals from database with optional filter |
| get_btc_arb_status | - | dict | Get BTC arbitrage engine status and current opportunities |
| update_btc_arb_config | request: dict | dict | Update BTC arbitrage engine configuration |
| execute_btc_arb | opportunity_id: str | dict | Manually execute BTC arbitrage opportunity |
| start_btc_arb | - | dict | Start BTC arbitrage engine |
| stop_btc_arb | - | dict | Stop BTC arbitrage engine |
| get_btc_arb_executions | limit: int = 50 | dict | Get BTC arbitrage execution history |
| get_raw_btc_markets | - | dict | Diagnostic: Get raw market data from KXBTC and KXBTCD series |
| get_ticker_patterns | - | dict | Diagnostic: Analyze ticker patterns in BTC markets with format breakdown |
| get_btc_arb_debug | - | dict | Diagnostic: Detailed BTC arbitrage scanner analysis with settlement matching |

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
HTTP client for Kalshi REST API with retry logic and batch orders

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| KalshiClient | - | - | Initialize with settings, create auth if credentials exist |
| KalshiClient._request | method, endpoint, params, json, max_retries | dict | Make authenticated HTTP request with exponential backoff retry |
| KalshiClient.get_markets | limit: int | List[Dict] | Fetch markets from Kalshi (status filter removed) |
| KalshiClient.get_market | ticker: str | Dict | Get single market by ticker |
| KalshiClient.get_orderbook | ticker: str, depth: int | Dict | Get orderbook for market |
| KalshiClient.get_events | series_ticker, status, with_nested_markets, limit | List[Dict] | Fetch events with mutually_exclusive flag for arbitrage |
| KalshiClient.get_balance | - | Dict | Get account balance |
| KalshiClient.get_positions | status: str | List[Dict] | Get portfolio positions |
| KalshiClient.place_order | ticker, side, action, count, price, order_type | Dict | Place single limit order on Kalshi |
| KalshiClient.place_batch_orders | orders: List[Dict] | Dict | Execute multiple orders atomically via batch endpoint |
| KalshiClient.get_fills | limit: int = 100 | List[Dict] | Get fill history from Kalshi API with trade details |
| KalshiClient.get_orders | status?: str, limit: int = 100 | List[Dict] | Get order history from Kalshi API with optional status filter |

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
| MarketClassifier.classify | market: dict | Tuple[MarketType, dict] | Parse market subtitle/title, return type and extracted data |

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
Route trades to paper simulation or live Kalshi with atomic execution

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| LiveTradeResult | trade_id, status, orders, costs, profit, message | dataclass | Live trade execution result |
| TradeExecutor | kalshi_client: KalshiClient | - | Initialize with Kalshi client and paper service |
| TradeExecutor.is_paper_mode | - | bool | Property: check if paper trading mode |
| TradeExecutor.get_balance | - | dict | Get balance from paper or Kalshi |
| TradeExecutor.get_positions | - | list | Get positions from paper or Kalshi |
| TradeExecutor.execute_arbitrage | opportunity, num_contracts | Union[Paper,Live]TradeResult | Route to paper or live execution |
| TradeExecutor._execute_live | opportunity, num_contracts | LiveTradeResult | Execute atomic batch orders on Kalshi |

### portfolio_service.py
Portfolio aggregation and order tracking across paper and live modes

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PortfolioService | - | - | Initialize with Kalshi client for live data |
| PortfolioService.get_summary | - | dict | Get paper/live balances and position counts |
| PortfolioService.get_all_positions | - | List[dict] | Fetch positions from SQLite (paper) and Kalshi API (live) |
| PortfolioService.get_orders | mode?: str, limit: int = 50 | List[dict] | Get manual order history with optional mode filtering |

### watchlist_service.py
Saved markets management with live price updates

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| WatchlistService | - | - | Initialize with Kalshi client for market fetching |
| WatchlistService.add | ticker: str, notes?: str | dict | Fetch market details from Kalshi and save to database |
| WatchlistService.remove | ticker: str | bool | Delete market from watchlist |
| WatchlistService.get_all | - | List[dict] | Get all watchlist items with fresh prices from Kalshi |

### edge_detector.py
Market edge detection using probability models

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| EdgeDetector | kalshi_client, db | - | Initialize with Kalshi client and database connection |
| EdgeDetector.load_config | - | None | Load minimum edge threshold from database |
| EdgeDetector.scan_btc_markets | - | List[TradingSignal] | Scan Bitcoin markets for pricing edges |
| EdgeDetector._analyze_btc_market | market: dict, current_btc: float | TradingSignal \| None | Analyze single BTC market for edge opportunities |
| EdgeDetector._parse_btc_strike | ticker: str | float \| None | Extract strike price from BTC market ticker |
| EdgeDetector._calculate_btc_probability | current: float, strike: float, market: dict | float | Calculate probability using logistic function |
| EdgeDetector._calculate_position_size | edge_percent: float | int | Kelly Criterion position sizing |
| EdgeDetector.save_signal | signal: TradingSignal | int | Save trading signal to database |
| EdgeDetector.get_pending_signals | - | List[dict] | Get all pending signals from database |
| TradingSignal | ticker, signal_type, edge_percent, model_prob, market_price, recommended_size, source | - | Dataclass for trading signal data |

### auto_trader.py
Automated trading engine with risk management

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| AutoTrader | kalshi_client, db | - | Initialize with Kalshi client and database connection |
| AutoTrader.load_config | - | None | Load configuration from database |
| AutoTrader.start | - | None | Start background trading loop |
| AutoTrader.stop | - | None | Stop background trading loop |
| AutoTrader.get_status | - | dict | Get current status and configuration |
| AutoTrader.update_config | **kwargs | dict | Update configuration parameters |
| AutoTrader.manual_scan | - | List[TradingSignal] | Run edge scan without executing trades |
| AutoTrader._run_loop | - | None | Main trading loop (runs every 60 seconds) |
| AutoTrader._scan_and_trade | - | None | Scan for edges and execute qualifying trades |
| AutoTrader._process_signal | signal: TradingSignal | None | Process single trading signal with risk checks |
| AutoTrader._has_position | ticker: str | bool | Check if already have position in market |
| AutoTrader._position_count | - | int | Count current open positions |
| AutoTrader._check_daily_loss | - | bool | Verify daily loss limit not exceeded |

### btc_arb_scanner.py
BTC arbitrage opportunity detection between range and threshold markets

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ArbLeg | ticker, market_type, side, action, price_cents, strike?, lower_bound?, upper_bound? | dataclass | Single leg of arbitrage trade |
| ArbOpportunity | id, event_date, settlement_time, legs, total_cost_cents, guaranteed_payout_cents, edge_cents, edge_percent | dataclass | Complete arbitrage opportunity data |
| BTCArbitrageScanner | kalshi_client | - | Scanner for BTC arbitrage between KXBTC/KXBTCD markets |
| BTCArbitrageScanner.scan | min_edge_percent: float = 3.0 | List[ArbOpportunity] | Scan for all profitable arbitrage opportunities |
| BTCArbitrageScanner._fetch_range_markets | - | List[Dict] | Fetch KXBTC range markets via get_events |
| BTCArbitrageScanner._fetch_threshold_markets | - | List[Dict] | Fetch KXBTCD threshold markets via get_events |
| BTCArbitrageScanner._check_range_arbitrage | range_mkt, thresh_lookup, event_date | ArbOpportunity? | Check single range for arbitrage vs thresholds |
| BTCArbitrageScanner._simplify_markets | markets: List[Dict], market_type: str | List[SimplifiedMarket] | Extract key fields from markets for UI display |
| BTCArbitrageScanner._calculate_arbitrage | range_mkt, thresh_lookup, event_date, min_edge | CalculationResult | Calculate arbitrage for single range with detailed breakdown |
| BTCArbitrageScanner._build_opportunity | range_mkt, thresh_lookup, event_date, calc | ArbOpportunity? | Build opportunity from profitable calculation result |
| BTCArbitrageScanner._build_threshold_lookup | thresholds: List[Dict] | Dict[float, Dict] | Build lookup of threshold markets by floor_strike with fuzzy keys |
| BTCArbitrageScanner._find_threshold | strike: float, lookup: Dict[float, Dict] | Optional[Dict] | Find threshold market with fuzzy matching on strike price |
| BTCArbitrageScanner.get_last_scan_result | - | ScanResult? | Get most recent complete scan result with all data |
| BTCArbitrageScanner.calculate_trade | opportunity, budget_cents | dict | Calculate trade details for given budget |
| BTCArbitrageScanner.get_stats | - | dict | Get scanner performance statistics |

### btc_arb_engine.py
Continuous BTC arbitrage scanning and execution engine

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| EngineConfig | min_edge_percent, budget_cents, auto_trade_enabled, mode, scan_interval_seconds | dataclass | Engine configuration parameters |
| EngineStatus | is_running, last_scan_at, opportunities_found, auto_executions, last_error | dataclass | Engine runtime status |
| BTCArbitrageEngine | kalshi_client, db | - | Background engine for continuous BTC arbitrage |
| BTCArbitrageEngine.start | - | None | Start background scanning loop |
| BTCArbitrageEngine.stop | - | None | Stop background scanning loop |
| BTCArbitrageEngine.get_status | - | dict | Get current engine status and config |
| BTCArbitrageEngine.get_full_status | - | dict | Get complete status including market data, categorized calculations (near_misses, profitable), and activity log |
| BTCArbitrageEngine.get_opportunities | - | List[dict] | Get current detected opportunities |
| BTCArbitrageEngine.update_config | **kwargs | dict | Update engine configuration |
| BTCArbitrageEngine.manual_execute | opportunity_id | dict | Manually execute specific opportunity |
| BTCArbitrageEngine._run_loop | - | None | Main scanning loop (every 2 seconds) |
| BTCArbitrageEngine._auto_execute | opportunity | None | Auto-execute best opportunity with safety controls |

---

## backend/utils/

### kalshi_auth.py
RSA-PSS authentication for Kalshi API

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| KalshiAuth | api_key_id: str, private_key_path: str | - | Load RSA private key for signing |
| KalshiAuth._load_key | path: str | RSAPrivateKey | Read and parse PEM private key |
| KalshiAuth.get_headers | method: str, path: str | dict | Generate signed auth headers with timestamp |

### logger.py
Logging utilities with console output and in-memory activity buffer for UI display

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ActivityBuffer | maxlen: int = 50 | - | Thread-safe circular buffer storing recent log messages |
| ActivityBuffer.add | level: str, message: str, emoji: str = "" | None | Add timestamped message to buffer |
| ActivityBuffer.get_all | - | List[Dict] | Get all messages in buffer (newest first) |
| ActivityBuffer.clear | - | None | Clear the buffer |
| ActivityHandler | buffer: ActivityBuffer | LogHandler | Custom logging handler writing to ActivityBuffer |
| setup_logger | name: str, activity_buffer: ActivityBuffer = None | Logger | Setup logger with console, file, and optional activity handlers |
| btc_arb_logger | - | Logger | Module-level logger for BTC arbitrage scanning |
| btc_arb_activity | - | ActivityBuffer | Module-level activity buffer for UI display |

---

## frontend/src/

### main.tsx
React application entry point

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| - | - | - | Render App in React.StrictMode to root element |

### App.tsx
Root application component with arbitrage hub navigation

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| App | - | JSX.Element | Main app with Header, TabNav (updated with Arbitrage tab), route to ArbitrageHub |

---

## frontend/src/hooks/

### useSpotPrice.ts
Live BTC spot price polling with source attribution

| Function/Type | Params | Returns | Description |
|----------|--------|---------|-------------|
| SpotPriceData | price, source, timestamp, isLive | interface | Spot price data with freshness indicator |
| UseSpotPriceResult | data, error, isLoading, refresh | interface | Hook return type |
| useSpotPrice | - | UseSpotPriceResult | Poll spot price every 15s, handle staleness |

---

## frontend/src/services/

### api.ts
Backend HTTP API client

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| fetchJson | url: string, options?: RequestInit | Promise<T> | Fetch JSON with error handling |
| api.getConfig | - | Promise<{paper_mode, api_configured}> | Get backend configuration |
| api.getSpotPrice | - | Promise<{asset, price, timestamp, source}> | Get current BTC spot price with source |
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
Application header with live spot price indicator

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| LiveIndicator | isLive: boolean | JSX.Element | Green pulse dot when live, yellow when stale |
| Header | - | JSX.Element | Display title, mode badge, live BTC price, balance |

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

## frontend/src/components/arbitrage/

### ArbitrageHub.tsx
Main arbitrage hub with sub-navigation

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ArbitrageHub | - | JSX.Element | Container with Crypto/Weather/Economic sub-tabs, route to section components |

### CryptoArbitrageSection.tsx
Crypto arbitrage scanner with card-based UI

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| CryptoArbitrageSection | - | JSX.Element | Two-mode UI: overview cards (BTC/ETH/SOL/XRP) and detailed scanner view |

### WeatherArbitrageSection.tsx
Weather arbitrage scanner with forecast highlighting

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| WeatherArbitrageSection | - | JSX.Element | 7-city grid with NWS forecasts, expandable bracket tables, forecast row highlighting |
| BracketTable | city, type, onTypeChange, onClose | JSX.Element | Modal table showing bracket prices with smart temperature parsing |

### shared/StatsBar.tsx
Reusable statistics display component

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| StatsBar | stats: StatItem[] | JSX.Element | Flexible stat boxes grid with dynamic columns and colors |

### shared/ConfigPanel.tsx
Reusable configuration controls component

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ConfigPanel | minEdge, budgetDollars, mode, autoTrade, callbacks | JSX.Element | Edge %, budget, paper/live mode, auto-trade controls |

### shared/OpportunityTable.tsx
Reusable opportunity table component

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| OpportunityTable | columns, data, handlers, renderers | JSX.Element | Generic table with click handlers, row highlighting, custom cell rendering |

---

## frontend/src/components/analytics/

### AnalyticsTab.tsx
Paper trading P&L analytics dashboard

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| AnalyticsTab | - | JSX.Element | Display P&L summary cards and details |

## frontend/src/components/portfolio/

### PortfolioTab.tsx
Portfolio overview with positions and order history

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PortfolioTab | - | JSX.Element | Display portfolio summary, positions table, order history with mode filters |

## frontend/src/components/trade/

### TradeCard.tsx
Manual trading market card interface

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| TradeCard | ticker: string | JSX.Element | Interactive market card with YES/NO prices, quantity input, mode selection, buy buttons |

### TradeTab.tsx
Manual trading tab wrapper

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| TradeTab | - | JSX.Element | Container for manual trading with hardcoded test market |

## frontend/src/components/watchlist/

### WatchlistTab.tsx
Saved markets management with live prices

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| WatchlistTab | - | JSX.Element | Add markets form, saved markets list with live prices and remove functionality |

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

### log_config.py
Centralized logging configuration with colored output

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ColoredFormatter | - | LogFormatter | Custom formatter with ANSI color codes for levels |
| setup_logging | service_name: str | Logger | Setup logger with console, file, and rotating handlers |

### log_viewer.py
Real-time log viewer with filtering and colored output

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| LogViewer | - | - | Log viewer with keyword filtering and color support |
| LogViewer.start | - | None | Start the log viewer main loop |

### nws_client.py
National Weather Service API client for forecast data

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| NWSClient | - | - | Client for NWS point forecast API |
| NWSClient.get_forecast | lat: float, lon: float | List[Dict] | Get 7-day forecast for coordinates |

### scanner_db.py
SQLite database for scanner results

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ScannerDatabase | db_path: Optional[str] | - | Database for scanner results and stats |
| ScannerDatabase.save_scanner_result | scanner_type: str, result: Dict | None | Save scanner result to database |
| ScannerDatabase.get_scanner_result | scanner_type: str | Optional[Dict] | Get latest scanner result |
| ScannerDatabase.get_scanner_stats | scanner_type: str | Dict | Get scanner performance statistics |

### scanner_service.py
Unified scanner service that runs all scanners

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ScannerService | - | - | Service running BTC and weather scanners |
| ScannerService.run_btc_scanner | - | None | Run BTC scanner loop every 2s |
| ScannerService.run_weather_scanner | - | None | Run weather scanner loop every 30s |
| ScannerService.start | - | None | Start all scanners concurrently |
| ScannerService.stop | - | None | Stop all running scanners |

### weather_arb_scanner.py
Weather arbitrage scanner for 14 market series (7 cities × 2 types)

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| WeatherArbScanner | kalshi_client | - | Scanner for weather market arbitrage opportunities |
| WeatherArbScanner.scan_once | - | Dict | Scan all 14 weather series for bracket arbitrage |
| WeatherArbScanner.get_nws_forecast | location_config | Optional[Dict] | Get NWS forecast for location |
| WeatherArbScanner.analyze_series | series_ticker, forecast_temp | Dict | Analyze single weather series for opportunities |

### fees.py
Kalshi fee calculation utilities

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| calculate_fees | subtotal: int | int | Calculate Kalshi trading fees in cents |

### locations/base.py
LocationConfig dataclass with forecast adjustments

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| LocationConfig | - | - | Weather location configuration with forecast adjustments |

### locations/registry.py
Weather location definitions for 7 major cities

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| get_location | code: str | LocationConfig | Get location config by code |
| get_all_locations | - | List[LocationConfig] | Get all 7 location configs |
| get_all_series | - | List[str] | Get all 14 series tickers (7 cities × 2 types) |

---

## frontend/src/types/

### weather.ts
Weather arbitrage TypeScript type definitions

| Interface/Type | Description |
|----------------|-------------|
| WeatherStatus | Main scanner status with cities, opportunities, forecasts, stats |
| CityResult | Single city data with high/low series results |
| SeriesResult | Temperature series with brackets, costs, opportunities |
| BracketMarket | Individual bracket with ticker, prices, volume |
| WeatherOpportunity | Arbitrage opportunity with profit calculations |
| ForecastData | NWS weather forecast with detailed descriptions |
| CostStatus | Union type: 'opportunity' \| 'near_miss' \| 'neutral' \| 'negative' |
| getCostStatus | cost: number \| null | CostStatus | Classify bracket total cost |
| getCostColor | status: CostStatus | string | Get Tailwind text color class |
| getCostBgColor | status: CostStatus | string | Get Tailwind background color class |
