# DIAGNOSTIC_FULL.md - Complete Backend Analysis

**Generated:** 2026-01-15
**Total:** 78 Python files, 22,905 lines

---

## 1. All Python Files with Line Counts

### backend/api/ (2,937 lines)
| File | Lines |
|------|-------|
| routes.py | 1,747 |
| prediction_routes.py | 545 |
| websocket_routes.py | 318 |
| schemas.py | 284 |
| websocket.py | 38 |
| __init__.py | 5 |

### backend/services/core/ (4,645 lines)
| File | Lines |
|------|-------|
| execution_gateway.py | 1,208 |
| strategy_orchestrator.py | 626 |
| fee_calculator.py | 602 |
| position_manager.py | 597 |
| backtest_engine.py | 511 |
| performance_tracker.py | 454 |
| batch_executor.py | 421 |
| signal_manager.py | 374 |
| alert_service.py | 350 |
| risk_manager.py | 330 |
| circuit_breaker.py | 303 |
| base_strategy.py | 285 |
| kelly_sizing.py | 248 |
| __init__.py | 158 |

### backend/services/strategies/ (1,388 lines)
| File | Lines |
|------|-------|
| weather_strategy.py | 631 |
| btc_directional_strategy.py | 490 |
| btc_arb_strategy.py | 267 |
| __init__.py | 135 |

### backend/services/analysis/ (2,054 lines)
| File | Lines |
|------|-------|
| arbitrage_calculator.py | 630 |
| prediction_engine_v2.py | 560 |
| probability_engine.py | 402 |
| position_calculator.py | 358 |
| __init__.py | 104 |

### backend/services/websocket/ (1,142 lines)
| File | Lines |
|------|-------|
| manager.py | 453 |
| data_sync.py | 380 |
| orderbook_builder.py | 295 |
| __init__.py | 14 |

### backend/services/nws/ (714 lines)
| File | Lines |
|------|-------|
| client.py | 472 |
| config.py | 212 |
| __init__.py | 30 |

### backend/services/reconciliation/ (402 lines)
| File | Lines |
|------|-------|
| reconciler.py | 376 |
| __init__.py | 26 |

### backend/services/ (Other - 2,350 lines)
| File | Lines |
|------|-------|
| btc_arb_scanner.py | 719 |
| weather_arb_scanner.py | 381 |
| paper_trading.py | 305 |
| kalshi_client.py | 302 |
| trade_executor.py | 218 |
| portfolio_service.py | 175 |
| log_config.py | 164 |
| nws_client.py | 155 |
| log_viewer.py | 136 |
| arbitrage_detector.py | 127 |
| spot_price_client.py | 123 |
| watchlist_service.py | 119 |
| scanner_db.py | 112 |
| market_classifier.py | 92 |
| arbitrage_calculator.py | 73 |
| __init__.py | 10 |

### backend/models/ (1,097 lines)
| File | Lines |
|------|-------|
| kalshi_models.py | 456 |
| nws_models.py | 281 |
| types.py | 141 |
| execution_models.py | 136 |
| __init__.py | 93 |
| schemas.py | 25 |

### backend/config/ (276 lines)
| File | Lines |
|------|-------|
| locations/registry.py | 120 |
| locations/base.py | 91 |
| __init__.py | 62 |
| locations/__init__.py | 3 |

### backend/database/ (238 lines)
| File | Lines |
|------|-------|
| migrations/001_execution_audit.py | 201 |
| connection.py | 33 |
| __init__.py | 3 |
| migrations/__init__.py | 1 |

### backend/utils/ (147 lines)
| File | Lines |
|------|-------|
| logger.py | 98 |
| kalshi_auth.py | 46 |
| __init__.py | 3 |

### backend/tests/ (2,330 lines)
| File | Lines |
|------|-------|
| test_integration.py | 528 |
| test_websocket.py | 503 |
| test_models.py | 502 |
| test_analysis.py | 414 |
| test_prediction_engine.py | 383 |
| __init__.py | 1 |

### backend/ (Root - 331 lines)
| File | Lines |
|------|-------|
| main.py | 331 |

---

## 2. Classes and Functions (Files >100 lines)

### backend/api/routes.py (1,747 lines)
```
47: def get_gateway(request)
58: async def get_config()
70: async def get_spot_price()
83: async def get_opportunities(...)
218: async def get_balance()
223: async def get_positions()
229: async def execute_arbitrage(...)
290: async def reset_paper(...)
296: async def paper_summary()
301: async def paper_trades(...)
307: async def settle_position(...)
314: async def place_trade(...)
380: async def get_market_details(...)
410: async def get_executions(...)
457: async def get_execution(...)
486: async def get_portfolio_summary()
492: async def get_portfolio_positions()
499: async def get_portfolio_orders(...)
508: async def get_watchlist()
515: async def add_to_watchlist(...)
522: async def remove_from_watchlist(...)
535: async def get_auto_trader_status()
562: async def update_auto_trader_config(...)
582: async def start_auto_trader()
595: async def stop_auto_trader()
608: async def manual_scan()
625: async def get_signals(...)
650: async def get_btc_arb_status()
709: async def update_btc_arb_config(...)
739: async def execute_btc_arb(...)
763: async def start_btc_arb_engine()
769: async def stop_btc_arb_engine()
775: async def get_btc_arb_executions(...)
788: async def get_raw_btc_markets()
824: async def get_ticker_patterns()
876: async def get_btc_arb_debug()
1024: async def get_weather_arb_status()
1033: async def get_weather_city(...)
1047: async def get_weather_arb_history(...)
1055: async def get_all_scanners_status()
1063: async def get_recent_logs(...)
1085: async def get_log_files()
1106: def get_orchestrator()
1112: def set_orchestrator(...)
1119: async def get_orchestrator_status()
1128: async def start_orchestrator()
1138: async def stop_orchestrator()
1148: async def set_orchestrator_auto_trade(...)
1158: async def set_orchestrator_mode(...)
1170: async def enable_strategy(...)
```

### backend/services/core/execution_gateway.py (1,208 lines)
```
67: class GatewayConfig
87: class CachedResult
94: class ExecutionGateway
```

### backend/services/btc_arb_scanner.py (719 lines)
```
21: class ArbLeg
37: class ArbOpportunity
71: class CalculationResult
108: class SimplifiedMarket
125: class ScanResult
145: class BTCArbitrageScanner
```

### backend/services/strategies/weather_strategy.py (631 lines)
```
36: class WeatherStrategy(BaseStrategy)
```

### backend/services/analysis/arbitrage_calculator.py (630 lines)
```
22: class ArbitrageStrategy(str, Enum)
31: class Market
45: class Event
53: class ArbitrageLeg
64: class StrategyResult
79: class ArbitrageAnalysis
91: class ArbitrageCalculator
617: def analyze_event(...)
625: def analyze_from_brackets(...)
```

### backend/services/core/strategy_orchestrator.py (626 lines)
```
24: class StrategyOrchestrator
```

### backend/services/core/fee_calculator.py (602 lines)
```
53: class FeeType(Enum)
70: class FeeCalculation
90: class FeeResult
104: class FeeCalculator
551: def calculate_fee(...)
572: def calculate_multi_leg_fee(...)
```

### backend/services/core/position_manager.py (597 lines)
```
47: class PositionSource(str, Enum)
56: class PositionConfig
74: class UnifiedPosition
111: class CachedPositions
119: class ExposureSummary
140: class PositionManager
```

### backend/services/analysis/prediction_engine_v2.py (560 lines)
```
22: class RecommendationAction(str, Enum)
31: class BracketAnalysis
84: class PredictionResult
111: class PositionInfo
119: class PredictionEngineV2
535: def get_engine(...)
551: def analyze_brackets(...)
```

### backend/services/core/backtest_engine.py (511 lines)
```
19: class BacktestConfig
32: class BacktestTrade
68: class BacktestResult
113: class BacktestEngine
```

### backend/services/strategies/btc_directional_strategy.py (490 lines)
```
42: class BTCDirectionalStrategy(BaseStrategy)
```

### backend/services/nws/client.py (472 lines)
```
38: class CircuitState(str, Enum)
46: class CircuitBreaker
98: class CacheEntry
126: class ForecastData
143: class NWSProductionClient
462: def get_client()
470: async def get_forecast(...)
```

### backend/models/kalshi_models.py (456 lines)
```
14: class OrderbookLevelModel(BaseModel)
24: class Orderbook(BaseModel)
180: class Market(BaseModel)
298: class Event(BaseModel)
369: class Position(BaseModel)
409: class Order(BaseModel)
```

### backend/services/core/performance_tracker.py (454 lines)
```
17: class Metrics
56: class PerformanceTracker
```

### backend/services/websocket/manager.py (453 lines)
```
28: class ConnectionState(str, Enum)
37: class Subscription
46: class WebSocketManager
```

### backend/services/core/batch_executor.py (421 lines)
```
19: class OrderSide(str, Enum)
25: class OrderAction(str, Enum)
31: class OrderStatus(str, Enum)
41: class OrderLeg
73: class BatchResult
102: class BatchExecutor
```

### backend/services/analysis/probability_engine.py (402 lines)
```
15: class WeatherPattern(str, Enum)
24: class BracketProbability
35: class ProbabilityEstimate
48: class MarketBracket
61: class NWSForecast
71: class ProbabilityEngine
388: def estimate_probabilities(...)
396: def estimate_from_dict(...)
```

### backend/services/weather_arb_scanner.py (381 lines)
```
27: class WeatherOpportunity
60: class WeatherArbScanner
```

### backend/services/websocket/data_sync.py (380 lines)
```
24: class MarketState
34: class DataSynchronizer
```

### backend/services/reconciliation/reconciler.py (376 lines)
```
26: class DiscrepancyType(str, Enum)
36: class Severity(str, Enum)
45: class Discrepancy
70: class ReconciliationConfig
80: class ReconciliationService
```

### backend/services/core/signal_manager.py (374 lines)
```
19: class SignalManager
```

### backend/services/analysis/position_calculator.py (358 lines)
```
16: class Position
32: class OrderbookLevel
39: class Orderbook
145: class OrderEffect
173: class PositionCalculator
351: def calculate_order_effect(...)
```

### backend/services/core/alert_service.py (350 lines)
```
17: class AlertType(str, Enum)
28: class AlertPriority(str, Enum)
37: class Alert
62: class AlertService
```

### backend/main.py (331 lines)
```
51: async def lifespan(app)
324: async def health()
```

### backend/services/core/risk_manager.py (330 lines)
```
17: class RiskLimits
28: class RiskCheck
36: class PositionState
45: class RiskManager
```

### backend/api/websocket_routes.py (318 lines)
```
18: class ConnectionManager
114: async def websocket_endpoint(...)
211: async def opportunities_websocket(...)
245: async def broadcast_orderbook_update(...)
263: async def broadcast_opportunity_update(...)
273: async def broadcast_risk_update(...)
282: async def broadcast_execution_update(...)
291: async def broadcast_alert(...)
300: async def broadcast_circuit_breaker_update(...)
311: def get_connection_manager()
316: def get_ws_stats()
```

### backend/services/paper_trading.py (305 lines)
```
14: class PaperOrderResult
25: class PaperTradeResult
39: class PaperTradingService
```

### backend/services/core/circuit_breaker.py (303 lines)
```
17: class TripReason(str, Enum)
31: class CBConfig
45: class CircuitBreakerStatus
78: class LossRecord
85: class CircuitBreaker
```

### backend/services/kalshi_client.py (302 lines)
```
14: class RateLimiter
46: class KalshiClient
```

### backend/services/websocket/orderbook_builder.py (295 lines)
```
23: class OrderbookLevelModel
30: class Orderbook
40: class OrderbookState
50: class OrderbookBuilder
```

### backend/api/schemas.py (284 lines)
```
13: class TradingMode(str, Enum)
18: class ArbitrageStrategy(str, Enum)
25: class OrderSide(str, Enum)
30: class OrderAction(str, Enum)
37: class ExecuteArbitrageRequest(BaseModel)
57: class SetTradingModeRequest(BaseModel)
66: class SubscribeMarketsRequest(BaseModel)
71: class ExecuteOpportunityRequest(BaseModel)
80: class MarketResponse(BaseModel)
97: class OrderbookLevelResponse(BaseModel)
103: class OrderbookResponse(BaseModel)
114: class ArbitrageLegResponse(BaseModel)
125: class ArbitrageOpportunityResponse(BaseModel)
143: class OpportunitiesResponse(BaseModel)
150: class ExecutionLegResult(BaseModel)
162: class ExecutionResponse(BaseModel)
178: class PositionResponse(BaseModel)
188: class CircuitBreakerResponse(BaseModel)
202: class RiskDashboardResponse(BaseModel)
228: class SystemStatusResponse(BaseModel)
241: class WSMessage(BaseModel)
248: class WSOrderbookUpdate(BaseModel)
255: class WSOpportunityUpdate(BaseModel)
261: class WSRiskUpdate(BaseModel)
267: class WSExecutionUpdate(BaseModel)
273: class WSSubscriptionConfirm(BaseModel)
280: class WSError(BaseModel)
```

### backend/services/core/base_strategy.py (285 lines)
```
14: class StrategyType(str, Enum)
21: class SignalType(str, Enum)
32: class SignalStatus(str, Enum)
43: class SignalLeg
56: class TradingSignal
199: class BaseStrategy(ABC)
```

### backend/models/nws_models.py (281 lines)
```
11: class WeatherPattern(str, Enum)
19: class ForecastPeriod(BaseModel)
51: class HourlyForecast(BaseModel)
71: class NWSForecast(BaseModel)
155: class ClimatologyData(BaseModel)
178: class LocationConfig(BaseModel)
```

### backend/services/strategies/btc_arb_strategy.py (267 lines)
```
37: class BTCArbitrageStrategy(BaseStrategy)
```

### backend/services/core/kelly_sizing.py (248 lines)
```
15: class KellyConfig
25: class KellyResult
34: class KellySizing
```

### backend/services/trade_executor.py (218 lines)
```
33: class LiveTradeResult
45: class TradeExecutor
```

### backend/services/nws/config.py (212 lines)
```
13: class GridPoint
93: class CacheConfig
116: class FallbackConfig
138: def get_grid_point(...)
151: def get_nws_forecast_url(...)
168: def get_open_meteo_params(...)
209: def normalize_city_code(...)
```

### backend/database/migrations/001_execution_audit.py (201 lines)
```
25: async def table_exists(...)
35: async def column_exists(...)
42: async def migrate_execution_audit(...)
77: async def migrate_circuit_breaker_state(...)
123: async def migrate_btc_arb_executions(...)
140: async def run_migration(...)
176: def main()
```

### backend/services/portfolio_service.py (175 lines)
```
15: class PortfolioService
```

### backend/services/log_config.py (164 lines)
```
35: class ColoredFormatter(logging.Formatter)
77: def setup_logging(...)
153: def shutdown_logging()
162: def get_logger(...)
```

### backend/services/nws_client.py (155 lines)
```
18: class WeatherForecast
31: class NWSClient
```

### backend/models/types.py (141 lines)
```
11: class MarketStatus(str, Enum)
21: class OrderSide(str, Enum)
26: class OrderAction(str, Enum)
31: class TimeInForce(str, Enum)
37: class ArbitrageStrategy(str, Enum)
45: class OrderbookLevel(TypedDict)
50: class MarketSnapshot(TypedDict)
66: class OrderbookSnapshot(TypedDict)
74: class PositionInfo(TypedDict)
82: class FeeResult(TypedDict)
88: class ArbitrageLeg(TypedDict)
97: class ArbitrageRecommendation(TypedDict)
112: class ValidationResult(TypedDict)
120: class ExecutionResult(TypedDict)
133: class CircuitBreakerStatus(TypedDict)
```

### backend/models/execution_models.py (136 lines)
```
14: class ExecutionLeg(BaseModel)
24: class ExecutionRequest(BaseModel)
89: class LegResult(BaseModel)
105: class ExecutionResult(BaseModel)
```

### backend/services/log_viewer.py (136 lines)
```
16: class Colors
31: class LogViewer
101: def main()
```

### backend/services/arbitrage_detector.py (127 lines)
```
11: class ArbitrageOpportunity
42: class ArbitrageDetector
```

### backend/services/spot_price_client.py (123 lines)
```
18: class SpotPrice
25: class SpotPriceClient
```

### backend/config/locations/registry.py (120 lines)
```
107: def get_location(...)
111: def get_all_locations()
115: def get_all_series()
```

### backend/services/watchlist_service.py (119 lines)
```
16: class WatchlistService
```

### backend/services/scanner_db.py (112 lines)
```
16: class ScannerDatabase
```

### backend/services/analysis/__init__.py (104 lines)
(exports and re-exports)

---

## 3. Internal Dependency Map

### Core Infrastructure Dependencies
```
backend/api/routes.py
  ← backend/services/analysis (PredictionEngineV2, ArbitrageCalculator, etc.)
  ← backend/services/core (ExecutionGateway, FeeCalculator, etc.)
  ← backend/models (execution_models, kalshi_models)
  ← backend/config/locations

backend/services/core/execution_gateway.py
  ← backend/models/execution_models
  ← backend/services/core/risk_manager
  ← backend/services/core/circuit_breaker
  ← backend/services/core/fee_calculator
  ← backend/services/core/alert_service

backend/services/strategies/weather_strategy.py
  ← backend/services/core/base_strategy
  ← backend/services/nws_client
  ← backend/services/core/fee_calculator (NOT USED - BUG!)

backend/services/strategies/btc_directional_strategy.py
  ← backend/services/core/base_strategy
  ← backend/services/spot_price_client
```

### Import Graph (Simplified)
```
main.py
  └── api/routes.py
      ├── services/core/execution_gateway.py
      │   ├── services/core/batch_executor.py
      │   ├── services/core/risk_manager.py
      │   ├── services/core/circuit_breaker.py
      │   └── services/core/fee_calculator.py
      ├── services/strategies/*.py
      │   └── services/core/base_strategy.py
      └── services/analysis/*.py
```

---

## 4. Database Tables Used

### Tables with Active Queries

| Table | Operations | Files |
|-------|------------|-------|
| `execution_audit` | SELECT, INSERT | routes.py, execution_gateway.py |
| `signals_v2` | SELECT, INSERT, UPDATE | signal_manager.py, routes.py |
| `trade_records` | SELECT, INSERT, UPDATE | performance_tracker.py |
| `paper_account` | SELECT, UPDATE | paper_trading.py |
| `paper_positions` | SELECT, INSERT, UPDATE, DELETE | paper_trading.py |
| `paper_trades` | SELECT, INSERT, DELETE | paper_trading.py |
| `orchestrator_config` | SELECT, INSERT OR REPLACE | strategy_orchestrator.py |
| `circuit_breaker_state` | CREATE, INSERT | migrations, circuit_breaker.py |
| `btc_arb_executions` | SELECT | routes.py |
| `historical_opportunities` | SELECT | backtest_engine.py |
| `scanner_results` | SELECT, INSERT OR REPLACE | scanner_db.py |
| `scanner_stats` | SELECT, INSERT | scanner_db.py |
| `watchlist` | SELECT, INSERT, UPDATE, DELETE | watchlist_service.py |
| `manual_orders` | SELECT | portfolio_service.py |

### Tables Defined in schema.sql (Not All Used)
- paper_account
- paper_positions
- paper_trades
- opportunity_history
- manual_orders
- watchlist
- trading_signals (v1 - legacy)
- auto_trader_config
- daily_pnl (v1 - legacy)
- btc_arb_executions
- btc_arb_config
- signals_v2
- trade_records
- orchestrator_config
- circuit_breaker_state
- risk_positions
- daily_pnl_v2
- historical_opportunities
- alert_history
- execution_audit

---

## 5. API Endpoints (72 Total)

### Main Routes (backend/api/routes.py)

| Method | Endpoint | Function |
|--------|----------|----------|
| GET | /config | get_config |
| GET | /spot-price | get_spot_price |
| GET | /opportunities | get_opportunities |
| GET | /balance | get_balance |
| GET | /positions | get_positions |
| POST | /execute | execute_arbitrage |
| POST | /paper/reset | reset_paper |
| GET | /paper/summary | paper_summary |
| GET | /paper/trades | paper_trades |
| POST | /paper/settle/{position_id} | settle_position |
| POST | /trade/place | place_trade |
| GET | /trade/market/{ticker} | get_market_details |
| GET | /executions | get_executions |
| GET | /executions/{audit_id} | get_execution |
| GET | /portfolio/summary | get_portfolio_summary |
| GET | /portfolio/positions | get_portfolio_positions |
| GET | /portfolio/orders | get_portfolio_orders |
| GET | /watchlist | get_watchlist |
| POST | /watchlist | add_to_watchlist |
| DELETE | /watchlist/{ticker} | remove_from_watchlist |
| GET | /auto-trader/status | get_auto_trader_status |
| POST | /auto-trader/config | update_auto_trader_config |
| POST | /auto-trader/start | start_auto_trader |
| POST | /auto-trader/stop | stop_auto_trader |
| GET | /auto-trader/scan | manual_scan |
| GET | /auto-trader/signals | get_signals |
| GET | /btc-arb/status | get_btc_arb_status |
| PUT | /btc-arb/config | update_btc_arb_config |
| POST | /btc-arb/execute/{opportunity_id} | execute_btc_arb |
| POST | /btc-arb/start | start_btc_arb_engine |
| POST | /btc-arb/stop | stop_btc_arb_engine |
| GET | /btc-arb/executions | get_btc_arb_executions |
| GET | /btc-arb/raw-markets | get_raw_btc_markets |
| GET | /btc-arb/ticker-patterns | get_ticker_patterns |
| GET | /btc-arb/debug | get_btc_arb_debug |
| GET | /weather-arb/status | get_weather_arb_status |
| GET | /weather-arb/city/{code} | get_weather_city |
| GET | /weather-arb/history | get_weather_arb_history |
| GET | /scanners/status | get_all_scanners_status |
| GET | /logs/recent | get_recent_logs |
| GET | /logs/files | get_log_files |
| GET | /orchestrator/status | get_orchestrator_status |
| POST | /orchestrator/start | start_orchestrator |
| POST | /orchestrator/stop | stop_orchestrator |
| POST | /orchestrator/auto-trade | set_orchestrator_auto_trade |
| POST | /orchestrator/mode | set_orchestrator_mode |
| POST | /orchestrator/strategy/{strategy_type}/enable | enable_strategy |
| POST | /orchestrator/scan | (line 1188) |
| POST | /orchestrator/execute/{signal_id} | (line 1208) |
| POST | /orchestrator/config | (line 1219) |
| GET | /signals | (line 1233) |
| GET | /signals/stats | (line 1283) |
| GET | /performance/metrics | (line 1296) |
| GET | /performance/daily | (line 1306) |
| GET | /performance/trades | (line 1315) |
| GET | /circuit-breaker/status | (line 1351) |
| POST | /circuit-breaker/reset | (line 1360) |
| POST | /circuit-breaker/trip | (line 1370) |
| POST | /emergency/kill | (line 1384) |
| POST | /emergency/resume | (line 1424) |
| GET | /emergency/status | (line 1465) |
| GET | /reconciliation/status | (line 1487) |
| POST | /reconciliation/run | (line 1495) |
| GET | /gateway/stats | (line 1519) |
| GET | /risk/status | (line 1540) |
| POST | /risk/sync | (line 1549) |
| GET | /alerts | (line 1565) |
| GET | /alerts/unacknowledged | (line 1574) |
| POST | /alerts/{alert_id}/acknowledge | (line 1583) |
| POST | /alerts/acknowledge-all | (line 1595) |
| GET | /alerts/stats | (line 1605) |
| POST | /backtest/run | (line 1618) |
| GET | /fees/calculate | (line 1663) |
| GET | /fees/table | (line 1691) |
| POST | /fees/analyze-arbitrage | (line 1717) |

### Prediction Routes (backend/api/prediction_routes.py)

| Method | Endpoint | Function |
|--------|----------|----------|
| GET | /predictions/cities | get_supported_cities |
| GET | /predictions/{city} | get_city_predictions |
| GET | /predictions/{city}/forecast | get_city_forecast |
| POST | /predictions/{city}/refresh | refresh_city_forecast |
| POST | /predictions/analyze | analyze_custom_brackets |
| GET | /predictions/status | get_prediction_status |
| POST | /predictions/reset-circuits | reset_prediction_circuits |

### WebSocket Routes (backend/api/websocket_routes.py)

| Type | Endpoint | Function |
|------|----------|----------|
| WS | /ws | websocket_endpoint |
| WS | /ws/opportunities | opportunities_websocket |

### Health Check (backend/main.py)

| Method | Endpoint | Function |
|--------|----------|----------|
| GET | /health | health |

---

## 6. Frontend Structure (frontend/src/)

### Total: 44 files, 7,697 lines

### Components (by size)
| File | Lines | Purpose |
|------|-------|---------|
| arbitrage/CryptoArbitrageSection.tsx | 771 | BTC arbitrage UI |
| btcarb/BTCArbitrageTab.tsx | 666 | BTC arb tab |
| arbitrage/hooks/useArbitrage.ts | 643 | Arbitrage data hooks |
| arbitrage/PredictionPanel.tsx | 560 | Weather predictions |
| arbitrage/RiskDashboard.tsx | 464 | Risk monitoring |
| arbitrage/PredictionTab.tsx | 443 | Prediction tab |
| arbitrage/ExecutionPanel.tsx | 438 | Trade execution |
| arbitrage/WeatherArbitrageSection.tsx | 390 | Weather arb UI |
| arbitrage/OrderBook.tsx | 389 | Order book display |
| autotrader/AutoTraderTab.tsx | 327 | Auto trading config |
| portfolio/PortfolioTab.tsx | 305 | Portfolio view |
| services/api.ts | 247 | API client |
| hooks/usePredictions.ts | 222 | Prediction hooks |
| watchlist/WatchlistTab.tsx | 216 | Watchlist |
| trade/TradeCard.tsx | 211 | Trade cards |
| types/weather.ts | 152 | Weather types |
| opportunities/ExecuteModal.tsx | 152 | Execution modal |
| arbitrage/ArbitrageAnalysisBox.tsx | 118 | Analysis display |
| trading/ModeToggle.tsx | 94 | Paper/live toggle |
| types/index.ts | 84 | Type definitions |
| opportunities/OpportunityCard.tsx | 79 | Opportunity card |
| arbitrage/shared/ConfigPanel.tsx | 79 | Config UI |
| arbitrage/shared/OpportunityTable.tsx | 76 | Opportunity list |
| opportunities/OpportunitiesTab.tsx | 67 | Opportunities tab |
| arbitrage/ArbitrageHub.tsx | 66 | Main arb hub |
| analytics/AnalyticsTab.tsx | 63 | Analytics |
| hooks/useSpotPrice.ts | 57 | BTC price hook |
| layout/Header.tsx | 57 | Header |
| App.tsx | 57 | Main app |
| trading/PositionList.tsx | 51 | Position list |
| layout/TabNav.tsx | 44 | Navigation |
| trading/TradeHistory.tsx | 42 | Trade history |
| trading/TradingTab.tsx | 39 | Trading tab |
| trading/ModeBanner.tsx | 39 | Mode indicator |
| arbitrage/index.ts | 31 | Exports |
| utils/format.ts | 30 | Formatters |
| stores/tradingStore.ts | 30 | Trading state |
| trade/TradeTab.tsx | 29 | Trade tab |
| stores/opportunityStore.ts | 26 | Opportunity state |
| arbitrage/shared/StatsBar.tsx | 22 | Stats display |
| common/Modal.tsx | 19 | Modal component |
| main.tsx | 10 | Entry point |
| index.css | 7 | Styles |
| vite-env.d.ts | 1 | Vite types |

### Directory Structure
```
frontend/src/
├── components/
│   ├── arbitrage/          # Main arbitrage UI (5 files, 2,585 lines)
│   │   ├── hooks/          # Data hooks
│   │   └── shared/         # Shared components
│   ├── btcarb/             # BTC arbitrage (1 file, 666 lines)
│   ├── autotrader/         # Auto trading (1 file, 327 lines)
│   ├── portfolio/          # Portfolio view (1 file, 305 lines)
│   ├── opportunities/      # Opportunities (3 files, 298 lines)
│   ├── watchlist/          # Watchlist (1 file, 216 lines)
│   ├── trade/              # Trade UI (2 files, 240 lines)
│   ├── trading/            # Trading controls (5 files, 265 lines)
│   ├── analytics/          # Analytics (1 file, 63 lines)
│   ├── layout/             # Layout (2 files, 101 lines)
│   └── common/             # Shared (1 file, 19 lines)
├── hooks/                  # Custom hooks (2 files, 279 lines)
├── services/               # API client (1 file, 247 lines)
├── stores/                 # Zustand stores (2 files, 56 lines)
├── types/                  # TypeScript types (2 files, 236 lines)
├── utils/                  # Utilities (1 file, 30 lines)
├── App.tsx                 # Main app (57 lines)
├── main.tsx                # Entry (10 lines)
└── index.css               # Styles (7 lines)
```

---

## Summary

- **Backend:** 78 Python files, 22,905 lines
- **Frontend:** 44 TS/TSX files, 7,697 lines
- **API Endpoints:** 72 REST + 2 WebSocket
- **Database Tables:** 20 defined, ~14 actively used
- **Core Classes:** 89 classes across all files
- **Strategies:** 3 (Weather, BTC Arb, BTC Directional)

### Known Issues
1. `weather_strategy.py` doesn't use `fee_calculator.py`
2. v1/v2 table duplication (legacy migration incomplete)
3. `routes.py` is 1,747 lines (should be split)
4. `execution_gateway.py` is 1,208 lines (complex)
