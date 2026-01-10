# Kalshi Trading Platform

Comprehensive trading platform for Kalshi prediction markets with manual trading, portfolio management, and arbitrage detection. Supports dual-mode execution (paper simulation + live trading), watchlists, and position tracking across multiple market types.

## Tech Stack

- FastAPI (Python backend API)
- React 18 + TypeScript (frontend)
- Zustand (state management)
- Tailwind CSS (styling)
- SQLite + aiosqlite (database)
- WebSockets (real-time updates)
- Cryptography (Kalshi RSA-PSS authentication)
- Vite (build tool)

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Scanners      │    │   Log Viewer    │
│   React/TS      │◄──►│   FastAPI       │◄──►│   BTC/Weather   │◄──►│   Colored       │
│   :5173         │    │   :8001         │    │   SQLite Write  │    │   Filter        │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
        │                      │                      │                        │
        ├─ App.tsx            ├─ main.py             ├─ run_scanners.py      ├─ run_logs.py
        ├─ Stores             ├─ API Routes          ├─ Scanner Service       ├─ Log Viewer
        ├─ Components         ├─ Services            ├─ Weather Scanner       └─ Filtering
        └─ Services           ├─ Database            └─ BTC Scanner
                              └─ Utils (Auth)
```

## Module Map

| Module | Path | Purpose |
|--------|------|---------|
| backend/api | backend/api/ | HTTP routes and WebSocket handlers |
| backend/database | backend/database/ | SQLite connection and schema |
| backend/models | backend/models/ | Pydantic request/response schemas |
| backend/services | backend/services/ | Core business logic and external integrations |
| backend/services/core | backend/services/core/ | Unified trading infrastructure (orchestrator, signals, risk, etc.) |
| backend/services/analysis | backend/services/analysis/ | Analysis tools and probability calculators |
| backend/services/execution | backend/services/execution/ | Order execution and validation components |
| backend/services/risk | backend/services/risk/ | Risk management and monitoring |
| backend/services/websocket | backend/services/websocket/ | WebSocket data synchronization |
| backend/tests | backend/tests/ | Unit and integration test suites |
| backend/utils | backend/utils/ | Kalshi RSA-PSS authentication |
| backend/config | backend/config/ | Settings and location configurations |
| frontend/components/arbitrage | frontend/src/components/arbitrage/ | Limited arbitrage components (hooks and exports) |
| frontend/hooks | frontend/src/hooks/ | Custom React hooks |
| frontend/services | frontend/src/services/ | Backend API client |
| frontend/stores | frontend/src/stores/ | Zustand state management |
| frontend/types | frontend/src/types/ | TypeScript type definitions |
| frontend/utils | frontend/src/utils/ | Formatting utilities |

## Entry Points

| File | Command | When to use |
|------|---------|-------------|
| backend/main.py | `uvicorn backend.main:app --reload` | Start FastAPI backend server |
| run_scanners.py | `python run_scanners.py` | Run weather and BTC scanners independently |
| run_logs.py | `python run_logs.py` | Run colored log viewer with filtering |
| test_core_components.py | `python test_core_components.py` | Test core trading infrastructure |

## File Tree

| File | Description |
|------|-------------|
| README.md | Project documentation and setup |
| ARCHITECTURE.md | 4-terminal architecture documentation |
| QUICKSTART.md | First time setup guide |
| docker-compose.yml | Docker container configuration |
| .claude/settings.local.json | Claude configuration settings |
| backend/main.py | FastAPI app entry point |
| backend/config.py | Legacy settings (replaced by config module) |
| backend/config/__init__.py | Pydantic settings with location configs |
| backend/config/fees.py | Kalshi fee calculation utilities |
| backend/config/locations/__init__.py | Location module exports |
| backend/config/locations/base.py | LocationConfig dataclass with forecast adjustments |
| backend/config/locations/registry.py | Weather location definitions (7 cities) |
| start.bat | Windows batch 4-terminal launcher script |
| stop.bat | Stop all Kalshi platform services |
| run_scanners.py | Scanner service entry point |
| run_logs.py | Log viewer entry point |
| test_core_components.py | Core trading infrastructure component test suite |
| backend/api/__init__.py | API module exports |
| backend/api/routes.py | REST API endpoint handlers |
| backend/api/schemas.py | API request/response schemas |
| backend/api/websocket.py | WebSocket connection manager |
| backend/api/websocket_routes.py | WebSocket route handlers |
| backend/database/__init__.py | Database module exports |
| backend/database/connection.py | SQLite async connection manager |
| backend/database/schema.sql | Table definitions for paper trading |
| backend/logging_config.py | Thread-safe logging with QueueHandler pattern |
| backend/models/__init__.py | Models module exports |
| backend/models/kalshi_models.py | Kalshi API data models with validation |
| backend/models/nws_models.py | Weather forecast and location models |
| backend/models/schemas.py | Pydantic request models |
| backend/models/types.py | TypedDict and Enum definitions |
| backend/services/__init__.py | Services module exports all classes |
| backend/services/arbitrage_calculator.py | Three-strategy arbitrage calculator for mutually exclusive brackets |
| backend/services/arbitrage_detector.py | Finds profitable arbitrage opportunities |
| backend/services/fee_calculator.py | Kalshi fee calculation logic |
| backend/services/kalshi_client.py | Kalshi REST API client |
| backend/services/market_classifier.py | Classifies markets as threshold/bracket |
| backend/services/paper_trading.py | Simulated paper trading service |
| backend/services/portfolio_service.py | Portfolio summary and position aggregation |
| backend/services/spot_price_client.py | Free API BTC price client (CoinGecko/CoinLore) |
| backend/services/trade_executor.py | Routes trades to paper or live |
| backend/services/watchlist_service.py | Saved markets management service |
| backend/services/edge_detector.py | Detects mispriced markets using probability models |
| backend/services/auto_trader.py | Automated trading engine with risk management |
| backend/services/btc_arb_scanner.py | BTC arbitrage opportunity detection scanner |
| backend/services/btc_arb_engine.py | Continuous BTC arbitrage scanning engine |
| backend/services/log_config.py | Centralized logging with colored output |
| backend/services/log_viewer.py | Real-time log viewer with filtering |
| backend/services/nws_client.py | National Weather Service API client |
| backend/services/scanner_db.py | SQLite database for scanner results |
| backend/services/scanner_service.py | Unified scanner service runner |
| backend/services/weather_arb_scanner.py | Weather arbitrage scanner for 14 series |
| backend/services/core/__init__.py | Core module exports all trading infrastructure |
| backend/services/core/base_strategy.py | BaseStrategy ABC and TradingSignal dataclass |
| backend/services/core/signal_manager.py | Signal lifecycle management and database storage |
| backend/services/core/kelly_sizing.py | Kelly Criterion position sizing calculator |
| backend/services/core/risk_manager.py | Position limits and loss tracking |
| backend/services/core/circuit_breaker.py | Emergency halt on consecutive losses |
| backend/services/core/batch_executor.py | Atomic multi-leg order execution |
| backend/services/core/performance_tracker.py | P&L tracking and metrics calculation |
| backend/services/core/alert_service.py | Real-time alerts via WebSocket |
| backend/services/core/strategy_orchestrator.py | Main trading engine coordinating all strategies |
| backend/services/core/backtest_engine.py | Historical strategy backtesting engine |
| backend/services/analysis/__init__.py | Analysis module exports |
| backend/services/analysis/arbitrage_calculator.py | Enhanced arbitrage calculator with fee handling |
| backend/services/analysis/fee_calculator.py | Advanced fee calculation engine |
| backend/services/analysis/position_calculator.py | Position sizing and portfolio calculations |
| backend/services/analysis/probability_engine.py | Weather probability modeling engine |
| backend/services/execution/__init__.py | Execution module exports |
| backend/services/execution/atomic_executor.py | Atomic multi-leg order execution |
| backend/services/execution/order_manager.py | Order lifecycle management |
| backend/services/execution/validator.py | Trade validation and safety checks |
| backend/services/risk/__init__.py | Risk module exports |
| backend/services/risk/circuit_breaker.py | Enhanced circuit breaker with multiple triggers |
| backend/services/risk/risk_monitor.py | Real-time risk monitoring service |
| backend/services/websocket/__init__.py | WebSocket module exports |
| backend/services/websocket/data_sync.py | Real-time data synchronization |
| backend/services/websocket/manager.py | WebSocket connection management |
| backend/services/websocket/orderbook_builder.py | Live orderbook construction |
| backend/tests/__init__.py | Test module exports |
| backend/tests/test_analysis.py | Analysis component unit tests |
| backend/tests/test_integration.py | Integration test suite |
| backend/tests/test_models.py | Data model unit tests |
| backend/tests/test_websocket.py | WebSocket functionality tests |
| backend/utils/__init__.py | Utils module exports |
| backend/utils/kalshi_auth.py | RSA-PSS signature authentication |
| backend/utils/logger.py | Logging system with activity buffer |
| frontend/postcss.config.js | PostCSS config for Tailwind |
| frontend/tailwind.config.js | Tailwind CSS configuration |
| frontend/vite.config.ts | Vite bundler configuration |
| frontend/src/vite-env.d.ts | Vite type definitions |
| frontend/src/components/arbitrage/hooks/useArbitrage.ts | Arbitrage data fetching and state management |
| frontend/src/components/arbitrage/index.ts | Arbitrage component exports |
| frontend/src/hooks/useSpotPrice.ts | Live BTC price polling hook |
| frontend/src/services/api.ts | Backend HTTP API client |
| frontend/src/stores/opportunityStore.ts | Opportunities Zustand store |
| frontend/src/stores/tradingStore.ts | Trading state Zustand store |
| frontend/src/types/index.ts | TypeScript interfaces |
| frontend/src/types/weather.ts | Weather arbitrage type definitions |
| frontend/src/utils/format.ts | Currency and time formatters |
| run_logs.py | Log viewer entry point |
| run_scanners.py | Scanner service entry point |
| test_core_components.py | Core trading infrastructure component test suite |
