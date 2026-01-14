# API Reference

## backend/

### main.py
FastAPI application entry point with lifespan management

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| lifespan | app: FastAPI | AsyncGenerator | Init database, auto-trader, BTC arbitrage engine, strategy orchestrator, print startup banner, handle shutdown |
| health | - | dict | Health check endpoint, returns status and paper mode |

### config.py
Application settings from environment variables

| Function/Property | Params | Returns | Description |
|----------|--------|---------|-------------|
| Settings | - | BaseSettings | Pydantic settings class with Kalshi/trading config |
| Settings.kalshi_ws_url | - | str | Property: derive WebSocket URL from API URL |
| Settings.has_kalshi_credentials | - | bool | Property: check if API key and private key exist |
| get_settings | - | Settings | Cached settings singleton via lru_cache |

### logging_config.py
Thread-safe logging with QueueHandler pattern to avoid Windows PermissionError

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| setup_logging | log_dir: str = "logs", log_level: int = INFO, max_bytes: int = 10MB, backup_count: int = 5, console_output: bool = True | Logger | Initialize thread-safe logging with queue-based rotation, call once at startup |
| shutdown_logging | - | None | Clean shutdown of logging system, called automatically via atexit |
| get_logger | name: str | Logger | Get named logger, use instead of logging.getLogger() |

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
| get_orchestrator_status | - | dict | Get orchestrator status including all strategies and components |
| start_orchestrator | - | dict | Start the orchestrator and all enabled strategies |
| stop_orchestrator | - | dict | Stop the orchestrator and all running strategies |
| set_orchestrator_auto_trade | enabled: bool | dict | Enable or disable auto-trading |
| set_orchestrator_mode | mode: str | dict | Set trading mode (paper or live) |
| enable_strategy | strategy_type: str, enabled: bool | dict | Enable or disable a specific strategy |
| trigger_manual_scan | strategy_type?: str | dict | Manually trigger a scan for signals |
| execute_signal | signal_id: str | dict | Manually execute a specific signal |
| save_orchestrator_config | - | dict | Save current orchestrator config to database |
| get_signals_v2 | strategy_type?, status?, limit | dict | Get signals from unified signals table |
| get_signal_stats | days: int = 7 | dict | Get signal statistics |
| get_performance_metrics | days: int = 30 | dict | Get performance metrics |
| get_daily_pnl | days: int = 30 | list | Get daily P&L history |
| get_trade_history | strategy_type?, status?, limit | dict | Get trade history |
| get_circuit_breaker_status | - | dict | Get circuit breaker status |
| reset_circuit_breaker | - | dict | Reset the circuit breaker |
| trip_circuit_breaker | reason: str | dict | Manually trip the circuit breaker |
| get_risk_status | - | dict | Get risk manager status |
| sync_risk_positions | - | dict | Sync risk manager positions with Kalshi |
| get_alerts | limit: int = 20 | dict | Get recent alerts |
| get_unacknowledged_alerts | limit: int = 50 | dict | Get unacknowledged alerts |
| acknowledge_alert | alert_id: str | dict | Acknowledge an alert |
| acknowledge_all_alerts | - | dict | Acknowledge all alerts |
| get_alert_stats | - | dict | Get alert statistics |
| run_backtest | request: dict | dict | Run a backtest on historical data |

### prediction_routes.py
Weather prediction and forecast API endpoints with rate limiting

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| get_supported_cities | - | dict | Get all supported cities with coordinates |
| get_predictions | city: str, force_refresh: bool = False | dict | Get complete prediction analysis for city |
| get_forecast | city: str, force_refresh: bool = False | dict | Get raw weather forecast for city |
| refresh_forecast | city: str | dict | Force refresh forecast from NWS/Open-Meteo |
| get_prediction_status | - | dict | Get circuit breaker status and cache info |
| reset_prediction_circuits | - | dict | Reset API circuit breakers |

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

### migrations/__init__.py
Database migrations module exports

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| - | - | - | Module exports for database migration utilities |

### migrations/001_execution_audit.py
Database migration for execution audit tables

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| migrate | - | - | Apply execution audit table schema changes |

---

## backend/models/

### execution_models.py
Execution and trade-related data models

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| - | - | - | Data models for trade execution, order management, and audit trails |

### schemas.py
Pydantic request/response models

| Class | Fields | Description |
|-------|--------|-------------|
| ExecuteRequest | opportunity_id: str, num_contracts: int | Request body for execute arbitrage endpoint |
| ResetRequest | starting_balance: Optional[float] | Request body for paper account reset |

### kalshi_models.py
Kalshi API data models with validation and business logic

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| OrderbookLevelModel | price_cents: int, quantity: int | - | Single orderbook level with price validation |
| Orderbook | ticker: str, yes_bids: List, no_bids: List | - | Complete orderbook with bid/ask calculation |
| Orderbook.yes_ask | - | Optional[int] | Price to buy YES (100 - best NO bid) |
| Orderbook.no_ask | - | Optional[int] | Price to buy NO (100 - best YES bid) |
| Orderbook.take_yes_cost | quantity: int | Dict | Calculate cost for YES quantity with multi-level fills |
| Orderbook.take_no_cost | quantity: int | Dict | Calculate cost for NO quantity with multi-level fills |
| Market | ticker: str, event_ticker: str, title: str, status: MarketStatus | - | Complete market data with 50+ validated fields |
| Market.bracket_label | - | str | Human-readable bracket description (e.g., "62-63°F") |
| Market.is_near_settlement | threshold_hours: float = 2.0 | bool | Check if market closes within threshold |
| Market.is_stale | max_age_seconds: float = 30.0 | bool | Check if market data is too old |
| Event | event_ticker: str, series_ticker: str, markets: List[Market] | - | Event with nested markets for arbitrage |
| Event.total_yes_cost | - | Optional[int] | Sum of all YES asks for arbitrage detection |
| Event.has_arbitrage_opportunity | - | bool | Quick check if sum < 100 cents |
| Position | ticker: str, position: int, total_cost_cents: int | - | User position with P&L calculations |
| Position.unrealized_pnl | current_price_cents: int | int | Calculate current unrealized P&L |
| Order | ticker: str, side: OrderSide, action: OrderAction | - | Order model with API payload conversion |
| Order.to_api_payload | - | dict | Convert to Kalshi API request format |

### nws_models.py
Weather forecast and location models

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ForecastPeriod | number: int, name: str, temperature: int | - | Single NWS forecast period |
| HourlyForecast | valid_time: datetime, temperature: int | - | Hourly temperature forecast point |
| NWSForecast | city: str, forecast_high: int, weather_pattern: WeatherPattern | - | Complete NWS forecast with uncertainty |
| NWSForecast.forecast_std_dev | - | float | Estimate standard deviation by weather pattern (1.5-5.0°F) |
| NWSForecast.max_hourly_temp | - | Optional[int] | Maximum temperature from hourly forecasts |
| NWSForecast.is_stale | max_age_hours: float = 1.0 | bool | Check if forecast data is too old |
| LocationConfig | city: str, series_ticker: str, latitude: float, longitude: float | - | Weather market location configuration |
| KALSHI_LOCATIONS | - | Dict[str, LocationConfig] | Pre-configured locations (NYC, CHI, MIA, AUS, LAX, DEN) |

### types.py
TypedDict definitions and enums for inter-component communication

| Type/Enum | Values/Fields | Description |
|-----------|---------------|-------------|
| MarketStatus | INITIALIZED, UNOPENED, OPEN, PAUSED, CLOSED, SETTLED | Market lifecycle states |
| OrderSide | YES, NO | Order side enumeration |
| OrderAction | BUY, SELL | Order action enumeration |
| ArbitrageStrategy | ALL_YES, ALL_NO, HYBRID, MIN_2_NO | Arbitrage strategy types |
| WeatherPattern | STABLE, TRANSITIONAL, STORMY, FRONTAL | Weather pattern for uncertainty |
| MarketSnapshot | ticker, event_ticker, status, prices, strikes | Market data snapshot |
| ArbitrageRecommendation | event_ticker, strategy, legs, costs, profit | Complete arbitrage recommendation |
| ExecutionResult | success, orders_filled, total_cost, slippage | Trade execution result |
| CircuitBreakerStatus | can_trade, reason, daily_pnl, consecutive_losses | Risk circuit breaker status |

---

## backend/services/

### kalshi_client.py
HTTP client for Kalshi REST API with rate limiting, idempotency support, and enhanced error handling

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| RateLimiter | max_requests: int = 10, window_seconds: float = 1.0 | - | Token bucket rate limiter for API requests |
| RateLimiter.acquire | - | None | Wait until request slot available (async) |
| KalshiClient | - | - | Initialize with settings, auth, read/write rate limiters |
| KalshiClient._request | method, endpoint, params, json, max_retries | dict | Rate-limited authenticated HTTP request with exponential backoff retry |
| KalshiClient.get_markets | limit: int | List[Dict] | Fetch markets from Kalshi (status filter removed) |
| KalshiClient.get_market | ticker: str | Dict | Get single market by ticker |
| KalshiClient.get_orderbook | ticker: str, depth: int | Dict | Get orderbook for market |
| KalshiClient.get_events | series_ticker, status, with_nested_markets, limit | List[Dict] | Fetch events with mutually_exclusive flag for arbitrage |
| KalshiClient.get_balance | - | Dict | Get account balance |
| KalshiClient.get_positions | status: str | List[Dict] | Get portfolio positions |
| KalshiClient.place_order | ticker, side, action, count, price, order_type, client_order_id? | Dict | Place single limit order with idempotency key and detailed error logging |
| KalshiClient.place_batch_orders | orders: List[Dict] | Dict | Execute multiple orders atomically with auto-generated idempotency keys |
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

### arbitrage_calculator.py
Three-strategy arbitrage analysis for mutually exclusive bracket markets

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ArbitrageCalculator | - | - | Calculator for bracket arbitrage strategies |
| ArbitrageCalculator.analyze | brackets: List[Dict[str, Any]] | Dict[str, Any] | Analyze all_yes, all_no, min_2_no strategies and return best |

### arbitrage_detector.py
Detect arbitrage opportunities between threshold and bracket markets

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ArbitrageOpportunity | id, asset, times, threshold, brackets, prices, costs, liquidity | dataclass | Complete arbitrage opportunity data |
| ArbitrageDetector | min_profit_pct, min_liquidity_usd | - | Detector with configurable thresholds |
| ArbitrageDetector.find_opportunities | groups: List[MarketGroup] | List[ArbitrageOpportunity] | Find all profitable arbitrage opportunities |
| ArbitrageDetector._analyze_threshold | threshold, brackets, group | Optional[ArbitrageOpportunity] | Analyze single threshold against brackets |


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

---

## backend/services/nws/

### config.py
NWS grid points configuration and cache settings

| Function/Constant | Params | Returns | Description |
|----------|--------|---------|-------------|
| NWS_GRID_POINTS | - | Dict[str, Tuple] | Hardcoded NWS grid coordinates for 7 cities (NYC, CHI, MIA, etc.) |
| CACHE_CONFIG | - | Dict | Adaptive cache TTL settings based on forecast age |
| FALLBACK_CONFIG | - | Dict | Open-Meteo API configuration for NWS fallback |

### client.py
Production NWS API client with Open-Meteo fallback and circuit breaker

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| NWSProductionClient | - | - | Production NWS client with fault tolerance |
| NWSProductionClient.get_forecast | city: str | NWSForecast | Get forecast with NWS primary, Open-Meteo fallback |
| NWSProductionClient._fetch_nws | city: str | Optional[NWSForecast] | Fetch from NWS API with grid point lookup |
| NWSProductionClient._fetch_open_meteo | city: str | NWSForecast | Fetch from Open-Meteo API as fallback |
| NWSProductionClient._determine_weather_pattern | data: dict | WeatherPattern | Classify weather pattern for uncertainty estimation |
| NWSProductionClient.get_circuit_status | - | Dict[str, str] | Get circuit breaker status for both APIs |
| NWSProductionClient.reset_circuits | - | None | Reset circuit breakers |

### scanner_db.py
SQLite database for scanner results

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ScannerDatabase | db_path: Optional[str] | - | Database for scanner results and stats |
| ScannerDatabase.save_scanner_result | scanner_type: str, result: Dict | None | Save scanner result to database |
| ScannerDatabase.get_scanner_result | scanner_type: str | Optional[Dict] | Get latest scanner result |
| ScannerDatabase.get_scanner_stats | scanner_type: str | Dict | Get scanner performance statistics |


### weather_arb_scanner.py
Weather arbitrage scanner for 14 market series (7 cities × 2 types)

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| WeatherArbScanner | kalshi_client | - | Scanner for weather market arbitrage opportunities |
| WeatherArbScanner.scan_once | - | Dict | Scan all 14 weather series for bracket arbitrage |
| WeatherArbScanner.get_nws_forecast | location_config | Optional[Dict] | Get NWS forecast for location |
| WeatherArbScanner.analyze_series | series_ticker, forecast_temp | Dict | Analyze single weather series for opportunities |

---

## backend/services/analysis/

### prediction_engine_v2.py
Enhanced weather prediction engine with fee-aware analysis and position awareness

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PredictionEngineV2 | min_edge=0.05, kelly_fraction=0.25, bankroll_cents=100000 | - | Initialize with risk parameters |
| PredictionEngineV2.analyze_brackets | brackets, forecast_high, forecast_std_dev, positions=[], city?, event_ticker? | PredictionResult | Complete bracket analysis with recommendations |
| PredictionEngineV2._bracket_probability | mean, std_dev, floor_strike, cap_strike | float | Calculate bracket probability using normal CDF |
| PredictionEngineV2._calculate_fee_aware_ev | prob, price_cents, side, contracts=10 | Tuple[float, float, float] | Calculate EV before/after fees |
| PredictionEngineV2._calculate_kelly | prob, price | float | Calculate Kelly fraction for position sizing |
| PredictionEngineV2._check_position_conflict | ticker, recommended_side, positions | bool | Check for opposing positions |
| PredictionEngineV2._norm_cdf | x, mean, std_dev | float | Normal cumulative distribution function |
| BracketAnalysis | ticker, model_probability, probability_edge, recommended_action, etc. | dataclass | Single bracket analysis result |
| PredictionResult | brackets, best_bracket, total_probability, warnings, etc. | dataclass | Complete prediction analysis result |

---

## backend/services/core/
Unified trading infrastructure module for all strategies

### base_strategy.py
Abstract base class for trading strategies

| Class/Enum | Values/Fields | Description |
|------------|---------------|-------------|
| StrategyType | WEATHER, BTC, ECONOMIC | Enum for strategy classification |
| SignalType | DIRECTIONAL, ARBITRAGE, SPREAD | Type of trading signal |
| SignalStatus | PENDING, EXECUTING, EXECUTED, REJECTED, EXPIRED, FAILED | Signal lifecycle status |
| SignalLeg | ticker, side, action, price_cents, strike?, bounds?, description | Single leg of multi-leg trade |
| TradingSignal | id, strategy_type, ticker, signal_type, edge_percent, model_prob, market_price, size, confidence, is_arbitrage, legs, status, timestamps | Complete trading signal data |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| BaseStrategy | - | ABC | Abstract base class for all trading strategies |
| BaseStrategy.scan | - | List[TradingSignal] | Abstract: Scan for opportunities |
| BaseStrategy.validate_signal | signal: TradingSignal | bool | Abstract: Validate signal is still tradeable |
| BaseStrategy.scan_interval_seconds | - | int | Abstract property: seconds between scans |
| BaseStrategy.get_status | - | dict | Get strategy status |
| BaseStrategy.run_scan | - | List[TradingSignal] | Run scan with error handling and logging |

### signal_manager.py
Signal lifecycle management and database storage

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| SignalManager | db | - | Initialize with database connection |
| SignalManager.create | signal, expires_in=300 | TradingSignal | Store new signal in database |
| SignalManager.get_pending | strategy_type?, limit=100 | List[TradingSignal] | Get pending signals sorted by edge |
| SignalManager.get_by_id | signal_id: str | TradingSignal? | Get signal by ID |
| SignalManager.update_status | signal_id, status, notes?, execution_price? | bool | Update signal status |
| SignalManager.has_recent | ticker, strategy_type, seconds=300 | bool | Check for duplicate signals |
| SignalManager.expire_old | - | int | Mark expired signals |
| SignalManager.get_history | strategy_type?, status?, limit=50 | List[TradingSignal] | Get signal history |
| SignalManager.get_stats | days=7 | dict | Get signal statistics |

### kelly_sizing.py
Kelly Criterion position sizing calculator

| Class | Fields | Description |
|-------|--------|-------------|
| KellyConfig | fraction=0.25, min_edge_percent=5.0, max_bet_percent=5.0, min/max_contracts | Configuration parameters |
| KellyResult | contracts, kelly_fraction, edge_percent, bet_percent, reason | Sizing calculation result |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| KellySizing | config: KellyConfig? | - | Initialize with optional config |
| KellySizing.calculate | model_prob, market_price_cents, bankroll_cents | KellyResult | Calculate optimal position size |
| KellySizing.calculate_arbitrage | total_cost_cents, payout_cents, bankroll_cents | int | Size for guaranteed profit |
| KellySizing.calculate_for_budget | model_prob, market_price_cents, budget_cents | KellyResult | Size within fixed budget |
| KellySizing.should_trade | model_prob, market_price_cents | tuple[bool, float] | Quick edge check |

### risk_manager.py
Position limits and loss tracking

| Class | Fields | Description |
|-------|--------|-------------|
| RiskLimits | max_position_per_market=100, max_total_position=500, max_daily_loss_cents=5000, max_single_trade_cents=1000 | Limit configuration |
| RiskCheck | approved: bool, reason: str, adjusted_size: int? | Trade approval result |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| RiskManager | limits: RiskLimits, db | - | Initialize with limits and database |
| RiskManager.check_trade | ticker, contracts, price_cents, balance_cents | RiskCheck | Check if trade passes limits |
| RiskManager.record_trade | ticker, contracts, price_cents | None | Record new position |
| RiskManager.record_pnl | pnl_cents | None | Record daily P&L |
| RiskManager.close_position | ticker, contracts | None | Update position on close |
| RiskManager.get_status | - | dict | Get current risk status |
| RiskManager.sync_positions | positions: List | None | Sync with Kalshi positions |

### circuit_breaker.py
Emergency halt on consecutive losses

| Class | Fields | Description |
|-------|--------|-------------|
| CBConfig | max_consecutive_losses=5, max_daily_loss_cents=5000, max_hourly_losses=3, cooldown_seconds=300 | Breaker configuration |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| CircuitBreaker | config: CBConfig? | - | Initialize with optional config |
| CircuitBreaker.can_trade | - | tuple[bool, str?] | Check if trading allowed |
| CircuitBreaker.record_result | won: bool, pnl_cents, ticker | None | Record trade outcome |
| CircuitBreaker.reset | - | None | Reset circuit breaker |
| CircuitBreaker.force_trip | reason: str | None | Manually trip breaker |
| CircuitBreaker.daily_reset | - | None | Reset daily counters |
| CircuitBreaker.get_status | - | dict | Get breaker status |

### batch_executor.py
Atomic multi-leg order execution

| Enum | Values | Description |
|------|--------|-------------|
| OrderSide | YES, NO | Order side |
| OrderAction | BUY, SELL | Order action |
| OrderStatus | PENDING, FILLED, PARTIAL, FAILED, CANCELLED | Order status |

| Class | Fields | Description |
|-------|--------|-------------|
| OrderLeg | ticker, side, action, contracts, price_cents, status, fill_price, filled_contracts, order_id, error, fee_cents | Single order leg |
| BatchResult | success, batch_id, legs, total_cost_cents, total_fees_cents, execution_ms, message, mode | Batch execution result |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| BatchExecutor | kalshi_client, paper_service?, fee_calculator? | - | Initialize with clients |
| BatchExecutor.execute | legs: List[OrderLeg], mode="paper", atomic=True | BatchResult | Execute batch of orders |
| BatchExecutor.execute_arbitrage | legs_data: List[Dict], contracts_per_leg, mode | BatchResult | Execute arbitrage trade |
| BatchExecutor.execute_single | ticker, side, action, contracts, price_cents, mode | BatchResult | Execute single order |
| BatchExecutor.estimate_cost | legs: List[OrderLeg] | dict | Estimate total cost and fees |

### performance_tracker.py
P&L tracking and metrics calculation

| Class | Fields | Description |
|-------|--------|-------------|
| Metrics | total_trades, winning_trades, losing_trades, win_rate, total_pnl_cents, total_fees_cents, profit_factor, sharpe_ratio, max_drawdown_percent, best_trade_cents, worst_trade_cents, avg_trade_pnl_cents | Performance metrics |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PerformanceTracker | db | - | Initialize with database |
| PerformanceTracker.record_trade | strategy_type, ticker, side, contracts, entry_price, fees_cents | str | Record trade entry, return trade_id |
| PerformanceTracker.record_exit | trade_id, exit_price | dict | Record trade exit with P&L |
| PerformanceTracker.record_arbitrage_exit | trade_id, payout_cents | dict | Record arbitrage settlement |
| PerformanceTracker.get_metrics | days=30 | Metrics | Calculate performance metrics |
| PerformanceTracker.get_daily_pnl | days=30 | List[dict] | Get daily P&L history |
| PerformanceTracker.get_strategy_breakdown | days=30 | dict | Get per-strategy metrics |
| PerformanceTracker.get_trades | strategy_type?, status?, limit=50 | dict | Get trade history |

### position_manager.py
Unified position tracking across paper and live modes with caching

| Enum | Values | Description |
|------|--------|-------------|
| PositionSource | PAPER, LIVE, BOTH | Source of position data |

| Class | Fields | Description |
|-------|--------|-------------|
| PositionConfig | cache_ttl_seconds, max_cache_entries, enable_caching, auto_refresh | Position manager configuration |
| UnifiedPosition | ticker, side, contracts, avg_price_cents, total_cost_cents, total_fees_cents, source, created_at, market_exposure_cents, settlement_time, metadata | Unified position representation |
| ExposureSummary | total_exposure_cents, position_count, total_cost_cents, total_fees_cents, by_side, by_ticker | Portfolio exposure summary |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PositionManager | kalshi_client, db, config? | - | Initialize with clients and optional config |
| PositionManager.get_positions | mode="paper", force_refresh=False | List[UnifiedPosition] | Get all positions for mode |
| PositionManager.get_position | ticker, mode="paper", force_refresh=False | Optional[UnifiedPosition] | Get position for specific ticker |
| PositionManager.has_position | ticker, mode="paper", side? | bool | Check if position exists |
| PositionManager.can_open_position | ticker, side, mode="paper" | Tuple[bool, str] | Validate Kalshi YES+NO constraint |
| PositionManager.get_exposure | mode="paper" | ExposureSummary | Get total portfolio exposure |
| PositionManager.get_positions_by_ticker_prefix | prefix, mode="paper" | List[UnifiedPosition] | Get positions matching prefix |
| PositionManager.get_position_count | mode="paper" | int | Count open positions |
| PositionManager.invalidate_cache | - | None | Clear live position cache |
| PositionManager.get_status | - | dict | Get status for dashboards |

### alert_service.py
Real-time alerts via WebSocket

| Enum | Values | Description |
|------|--------|-------------|
| AlertType | OPPORTUNITY, TRADE_EXECUTED, TRADE_FAILED, CIRCUIT_BREAKER, RISK_WARNING, ERROR, INFO | Alert type |
| AlertPriority | LOW, MEDIUM, HIGH, CRITICAL | Alert priority |

| Class | Fields | Description |
|-------|--------|-------------|
| Alert | id, type, title, message, priority, timestamp, data, acknowledged | Alert data |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| AlertService | websocket_manager?, max_history=100 | - | Initialize with optional WS manager |
| AlertService.send | alert_type, title, message, priority, data? | Alert | Send alert notification |
| AlertService.opportunity | ticker, edge_percent, strategy, data? | Alert | Send opportunity alert |
| AlertService.trade_executed | ticker, contracts, price_cents, pnl_cents, mode, data? | Alert | Send trade executed alert |
| AlertService.trade_failed | ticker, reason, data? | Alert | Send trade failed alert |
| AlertService.circuit_breaker | tripped: bool, reason, data? | Alert | Send circuit breaker alert |
| AlertService.risk_warning | warning_type, message, data? | Alert | Send risk warning alert |
| AlertService.get_recent | limit=20 | List[dict] | Get recent alerts |
| AlertService.get_unacknowledged | limit=50 | List[dict] | Get unacknowledged alerts |
| AlertService.acknowledge | alert_id | bool | Acknowledge alert |
| AlertService.acknowledge_all | - | int | Acknowledge all alerts |
| AlertService.get_stats | - | dict | Get alert statistics |

### strategy_orchestrator.py
Main trading engine coordinating all strategies

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| StrategyOrchestrator | db, signals, kelly, risk, circuit, executor, performance, alerts | - | Initialize with all components |
| StrategyOrchestrator.register | strategy: BaseStrategy | None | Register a trading strategy |
| StrategyOrchestrator.unregister | strategy_type: StrategyType | bool | Unregister a strategy |
| StrategyOrchestrator.start | - | None | Start orchestrator and enabled strategies |
| StrategyOrchestrator.stop | - | None | Stop orchestrator and all tasks |
| StrategyOrchestrator.enable_strategy | strategy_type, enabled=True | bool | Enable or disable strategy |
| StrategyOrchestrator.set_auto_trade | enabled: bool | None | Set auto-trade mode |
| StrategyOrchestrator.set_mode | mode: str | None | Set paper or live mode |
| StrategyOrchestrator.get_status | - | dict | Get complete orchestrator status |
| StrategyOrchestrator.manual_scan | strategy_type? | List[dict] | Manually trigger scan |
| StrategyOrchestrator.manual_execute | signal_id: str | dict | Execute specific signal |
| StrategyOrchestrator.load_config | - | None | Load config from database |
| StrategyOrchestrator.save_config | - | None | Save config to database |

### backtest_engine.py
Historical strategy backtesting engine

| Class | Fields | Description |
|-------|--------|-------------|
| BacktestConfig | start_date, end_date, initial_balance_cents=100000, kelly_fraction=0.25, min_edge_percent=5.0, max_position_per_trade=100, slippage_cents=1 | Backtest configuration |
| BacktestTrade | signal_id, ticker, strategy_type, entry/exit_time, entry/exit_price, contracts, side, is_arbitrage, pnl_cents, fees_cents, status | Simulated trade record |
| BacktestResult | config, final_balance_cents, total_trades, winning/losing_trades, win_rate, total_pnl_cents, total_fees_cents, max_drawdown_percent, sharpe_ratio, profit_factor, equity_curve, trades, strategy_breakdown, errors | Backtest result |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| BacktestEngine | db | - | Initialize with database |
| BacktestEngine.run | strategy: BaseStrategy, config: BacktestConfig | BacktestResult | Run backtest for single strategy |
| BacktestEngine.run_multiple | strategies: List[BaseStrategy], config | Dict[str, BacktestResult] | Run backtest for multiple strategies |

### execution_gateway.py
Single entry point for all trade execution with risk checks, price validation, and position conflict detection

| Class | Fields | Description |
|-------|--------|-------------|
| GatewayConfig | idempotency_ttl_seconds=300, max_cache_size=1000, require_risk_check=True, require_circuit_check=True, default_timeout_seconds=30.0 | Gateway configuration |

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ExecutionGateway | kalshi_client, paper_service, risk_manager, circuit_breaker, fee_calculator, db, alert_service, config?, position_manager? | - | Initialize unified execution gateway with position cache invalidation |
| ExecutionGateway.execute | request: ExecutionRequest | ExecutionResult | Execute trade with full pipeline: idempotency, validation, price re-validation, risk checks, position conflicts |
| ExecutionGateway.execute_single | ticker, side, action, contracts, price_cents, mode="paper", source="manual" | ExecutionResult | Execute single order with full pipeline |
| ExecutionGateway.execute_arbitrage | legs: List[dict], contracts_per_leg: int, mode="paper", source="strategy" | ExecutionResult | Execute arbitrage trade with validation |
| ExecutionGateway._check_position_conflicts | request: ExecutionRequest | None | Validate no YES+NO conflicts on same market |
| ExecutionGateway._revalidate_prices | request: ExecutionRequest, max_slippage_cents=2 | bool | Check prices haven't moved beyond slippage |
| ExecutionGateway.get_status | - | dict | Get gateway configuration and cache status |
| ExecutionGateway.get_recent_audits | limit=50 | List[Dict] | Get execution audit history |
| ExecutionGateway.clear_cache | - | int | Clear idempotency cache, return cleared count |

### fee_calculator.py
Consolidated fee calculation service

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| FeeCalculator | - | - | Initialize consolidated fee calculator |
| FeeCalculator.calculate | contracts: int, price_cents: int, fee_type: FeeType = TAKER | FeeCalculation | Calculate fee for a single trade |
| FeeCalculator.calculate_multi_leg | legs: List[Dict[str, Any]], fee_type: FeeType = TAKER | Dict[str, Any] | Calculate fees for multiple trade legs with per-leg precision |
| FeeCalculator.estimate_arbitrage_profit | legs: List[Dict[str, Any]], payout_cents: int = 100, fee_type: FeeType = TAKER | Dict[str, Any] | Estimate profit from arbitrage opportunity |
| FeeCalculator.analyze_weather_arbitrage | yes_asks: List[int], no_asks: List[int], order_type: FeeType = TAKER | Dict[str, Any] | Analyze all three weather bracket arbitrage strategies |

---

## backend/tests/

### test_prediction_engine.py
Comprehensive test suite for prediction engine v2

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| TestProbabilityCalculations | - | - | Test probability calculations using normal distribution CDF |
| TestFeeAwareEV | - | - | Test fee-aware expected value calculations |
| TestPositionAwareness | - | - | Test position conflict detection |
| TestKellySizing | - | - | Test Kelly criterion position sizing |
| TestEdgeThreshold | - | - | Test minimum edge threshold requirements |
| TestAnalyzeBrackets | - | - | Test main analyze_brackets method |
| TestNormCDF | - | - | Test normal CDF implementation |

---

## backend/config/

### __init__.py
Pydantic settings with location configurations

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| Settings | - | BaseSettings | Application settings with Kalshi API, trading, scanner, database, and logging config |
| Settings.has_kalshi_credentials | - | bool | Property: check if API key and private key path exist |
| get_settings | - | Settings | Cached settings singleton via lru_cache |

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

## backend/services/reconciliation/

### reconciler.py
Position and balance reconciliation service to detect discrepancies between local state and Kalshi

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| DiscrepancyType | - | Enum | Types of discrepancies: missing_local, missing_remote, quantity_mismatch, balance_mismatch |
| Severity | - | Enum | Severity levels: info, warning, critical |
| Discrepancy | type: DiscrepancyType, severity: Severity, ticker: str, details: dict | dataclass | Represents a detected discrepancy with context |
| ReconciliationConfig | run_interval_seconds: int = 300, critical_threshold_cents: int = 1000, halt_on_critical: bool = True, auto_start: bool = False | dataclass | Configuration for reconciliation behavior |
| ReconciliationService.__init__ | kalshi_client, position_manager, alert_service, circuit_breaker, db, config: Optional[ReconciliationConfig] | - | Initialize reconciliation service with dependencies |
| ReconciliationService.start | - | None | Start automated reconciliation loop |
| ReconciliationService.stop | - | None | Stop reconciliation loop |
| ReconciliationService.reconcile_now | mode: str = "live" | List[Discrepancy] | Run immediate reconciliation and return discrepancies found |

## backend/services/strategies/

### __init__.py
Strategy module exports with registry system

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| register_strategy | strategy_class | function | Decorator to register strategy classes with their type |
| get_strategy_class | strategy_type: StrategyType | Type[BaseStrategy] | Get strategy class by type (last registered wins) |
| get_all_strategies | - | Dict[StrategyType, Type[BaseStrategy]] | Get mapping of all registered strategies |
| get_registered_types | - | List[StrategyType] | Get list of all registered strategy types |
| get_all_strategy_classes | - | List[Type[BaseStrategy]] | Get all strategy classes regardless of type overlap |

### btc_arb_strategy.py
BTC arbitrage strategy for range vs threshold markets

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| BTCArbitrageStrategy.__init__ | kalshi_client, min_edge_percent: float = 3.0, scan_interval: float = 5.0 | - | Initialize BTC arbitrage strategy with configuration |
| BTCArbitrageStrategy.scan | - | List[TradingSignal] | Scan for BTC arbitrage opportunities between range/threshold markets |

### btc_directional_strategy.py
BTC directional strategy using logistic probability model

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| BTCDirectionalStrategy.__init__ | kalshi_client, spot_client: Optional[SpotPriceClient], min_edge_percent: float = 8.0, base_volatility_percent: float = 1.5, scan_interval: float = 10.0 | - | Initialize BTC directional strategy with logistic model |
| BTCDirectionalStrategy.scan | - | List[TradingSignal] | Scan for mispriced BTC threshold markets using logistic probability |

### weather_strategy.py
Weather bracket arbitrage and directional trading strategy

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| WeatherStrategy.__init__ | kalshi_client, nws_client: Optional[NWSClient], min_edge_percent: float = 3.0, min_directional_edge: float = 5.0, scan_interval: float = 30.0 | - | Initialize weather strategy with NWS integration |
| WeatherStrategy.scan | - | List[TradingSignal] | Scan weather markets for bracket arbitrage and directional opportunities |

---

## Root Scripts and Utilities

### diagnose_infrastructure.py
Comprehensive infrastructure diagnostic tool for database schema, component imports, and system validation

| Function/Class | Params | Returns | Description |
|----------|--------|---------|-------------|
| Colors | - | - | ANSI color codes class for colored terminal output |
| log_ok | msg: str | None | Print success message in green |
| log_fail | msg: str, details: str = "" | None | Print failure message in red with optional details |
| log_warn | msg: str, details: str = "" | None | Print warning message in yellow |
| log_info | msg: str, details: str = "" | None | Print info message in cyan |
| DiagnosticSuite | - | - | Main diagnostic coordinator class |
| DiagnosticSuite.run | fix_issues: bool = False, verbose: bool = False | bool | Run complete diagnostic suite with optional fixes |
| DiagnosticSuite._check_database | - | Tuple[bool, List[str]] | Verify database schema and tables |
| DiagnosticSuite._check_component_imports | - | Tuple[bool, List[str]] | Test all component imports |
| DiagnosticSuite._check_component_instantiation | - | Tuple[bool, List[str]] | Test component creation |
| DiagnosticSuite._run_core_tests | - | Tuple[bool, List[str]] | Execute core component tests |
| DiagnosticSuite._fix_database_issues | issues: List[str] | bool | Attempt to fix database schema problems |
| DiagnosticSuite._generate_summary_report | results: Dict | None | Generate DIAGNOSTIC_SUMMARY.md report |
| main | - | int | CLI entry point with argument parsing |

### test1.py
Quick validation test suite for new trading infrastructure components

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| log_pass | msg: str | None | Record and display passed test |
| log_fail | msg: str, error: str = None | None | Record and display failed test with optional error |
| log_warn | msg: str | None | Record and display warning |
| section | title: str | None | Print formatted test section header |
| test_imports | - | None | Test import of all infrastructure modules |
| test_component_creation | - | None | Test instantiation of core components |
| test_database_operations | - | None | Test database connectivity and operations |
| test_signal_lifecycle | - | None | Test trading signal creation and management |
| test_execution_pipeline | - | None | Test order execution pathway |
| test_risk_management | - | None | Test risk manager and circuit breaker |
| test_performance_tracking | - | None | Test performance metrics calculation |
| main | - | int | Main test runner with summary reporting |

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

### usePredictions.ts
Weather prediction data fetching hook with auto-refresh

| Function/Type | Params | Returns | Description |
|----------|--------|---------|-------------|
| UsePredictionsResult | data, loading, error, lastUpdated, refresh | interface | Hook return type |
| usePredictions | city: string | UsePredictionsResult | Fetch predictions with 5-minute auto-refresh |

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

### ArbitrageAnalysisBox.tsx
Three-strategy arbitrage analysis display component

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| StrategyCard | label, strategy, isBest | JSX.Element | Individual strategy card with cost/profit/status display |
| ArbitrageAnalysisBox | arbitrage: ArbitrageAnalysis | JSX.Element | Display all_yes, all_no, min_2_no strategies with best strategy highlighting |

### CryptoArbitrageSection.tsx
Crypto arbitrage scanner with card-based UI

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| CryptoArbitrageSection | - | JSX.Element | Two-mode UI: overview cards (BTC/ETH/SOL/XRP) and detailed scanner view |

### WeatherArbitrageSection.tsx
Weather arbitrage scanner with forecast highlighting and bracket sorting

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| getBracketLabel | bracket: BracketMarket | string | Extract temperature label from Kalshi title (e.g., "be 61-62°" → "61-62°F") |
| sortBrackets | brackets: BracketMarket[] | BracketMarket[] | Sort brackets by floor_strike ascending (open-ended lower first, then ranges, then open-ended upper) |
| isForecastInBracket | bracket: BracketMarket, forecastTemp: number | boolean | Check if forecast temperature falls within bracket's floor_strike to cap_strike range |
| WeatherArbitrageSection | - | JSX.Element | 7-city grid with NWS forecasts, expandable bracket tables, forecast row highlighting |
| BracketTable | city, type, onTypeChange, onClose | JSX.Element | Modal table showing sorted bracket prices with forecast highlighting using Kalshi strike fields |

### ExecutionPanel.tsx
Trade execution panel with order management and risk controls

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ExecutionPanel | opportunity, onExecute, onCancel | JSX.Element | Order execution interface with position sizing, slippage controls, and execution confirmation |

### OrderBook.tsx
Real-time order book display component

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| OrderBook | ticker: string | JSX.Element | Live order book with bid/ask levels, depth visualization, and price updates |

### PredictionPanel.tsx
Weather prediction analysis panel with NWS integration

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PredictionPanel | city: string, marketType: 'high' \| 'low' | JSX.Element | Forecast display with temperature probabilities and bracket recommendations |

### PredictionTab.tsx
Weather prediction tab interface with city selection

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| PredictionTab | - | JSX.Element | City selection interface with forecast analysis and market recommendations |

### RiskDashboard.tsx
Risk monitoring and circuit breaker dashboard

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| RiskDashboard | - | JSX.Element | Real-time risk metrics, position limits, circuit breaker status, and manual controls |

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

## Root Scripts

### start.bat
Windows batch 4-terminal launcher

| Description |
|-------------|
| Launch frontend, backend, scanners, and log viewer in Windows Terminal tabs |

### test_integration_startup.py
Integration test suite verifying complete application startup

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| wait_for_startup | proc: subprocess.Popen, timeout: int = 20 | bool | Wait for server to be ready by polling health endpoint |
| test_endpoint | name: str, method: str, path: str, expected_status: int = 200, json_body: dict = None | bool | Test single API endpoint with timeout and status validation |
| main | - | int | Start server on port 8099, test all endpoints, cleanup on exit |

---

## frontend/src/types/

### weather.ts
Weather arbitrage TypeScript type definitions

| Interface/Type | Description |
|----------------|-------------|
| WeatherStatus | Main scanner status with cities, opportunities, forecasts, stats |
| CityResult | Single city data with high/low series results |
| SeriesResult | Temperature series with brackets, costs, opportunities |
| BracketMarket | Individual bracket with ticker, floor_strike, cap_strike, prices, volume |
| WeatherOpportunity | Arbitrage opportunity with profit calculations |
| ForecastData | NWS weather forecast with detailed descriptions |
| CostStatus | Union type: 'opportunity' \| 'near_miss' \| 'neutral' \| 'negative' |
| getCostStatus | cost: number \| null | CostStatus | Classify bracket total cost |
| getCostColor | status: CostStatus | string | Get Tailwind text color class |
| getCostBgColor | status: CostStatus | string | Get Tailwind background color class |
