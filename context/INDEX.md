# Kalshi Arbitrage Trading Platform - Index

## Overview

Automated prediction market arbitrage detection and execution on Kalshi with paper trading simulation. Features weather bracket arbitrage, BTC threshold/range arbitrage, and directional trading strategies.

**Version**: 2.0 (Unified Trading Infrastructure)
**Last Updated**: 2026-01-15

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | FastAPI 0.109.0 | REST API server |
| Frontend | React 18 + TypeScript | Web UI |
| State | Zustand 4.x | Client state management |
| Styling | Tailwind CSS 3.x | UI styling |
| Database | SQLite + aiosqlite 0.19.0 | Local storage |
| Auth | cryptography (RSA-PSS) | Kalshi API auth |
| HTTP | httpx 0.26.0 | Async HTTP client |
| Build | Vite 5.x | Frontend bundler |

## Architecture (4-Terminal)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Terminal 1    │    │   Terminal 2    │    │   Terminal 3    │    │   Terminal 4    │
│   Frontend      │◄──►│   Backend API   │◄──►│   Scanners      │    │   Log Viewer    │
│   React/Vite    │    │   FastAPI       │    │   BTC/Weather   │    │   Colored logs  │
│   :5173         │    │   :8001         │    │   SQLite Write  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Entry Points

| File | Command | Purpose |
|------|---------|---------|
| `backend/main.py` | `uvicorn backend.main:app --reload --port 8001` | Start API server |
| `frontend/` | `npm run dev` (in frontend/) | Start React dev server |
| `run_scanners.py` | `python run_scanners.py` | Run BTC + Weather scanners |
| `run_logs.py` | `python run_logs.py` | Start log viewer |
| `start.bat` | `start.bat` | Launch all 4 terminals |
| `test_core_components.py` | `python test_core_components.py` | Test core infrastructure |

## Module Map

### Backend Core

| Module | Path | Purpose | Status |
|--------|------|---------|--------|
| API Routes | `backend/api/routes.py` | REST endpoints (72 endpoints) | Working |
| Prediction Routes | `backend/api/prediction_routes.py` | Weather prediction API | Working |
| WebSocket | `backend/api/websocket_routes.py` | Real-time updates | Working |
| Main Entry | `backend/main.py` | FastAPI app initialization | Working |

### Services - Core Trading Infrastructure

| Module | Path | Purpose | Status |
|--------|------|---------|--------|
| Strategy Orchestrator | `backend/services/core/strategy_orchestrator.py` | Main trading engine | Working |
| Execution Gateway | `backend/services/core/execution_gateway.py` | Single entry point for trades | **BUG: Cache invalidation** |
| Batch Executor | `backend/services/core/batch_executor.py` | Multi-leg atomic execution | **BUG: No rollback** |
| Signal Manager | `backend/services/core/signal_manager.py` | Signal lifecycle | Working |
| Position Manager | `backend/services/core/position_manager.py` | Position tracking | Working |
| Risk Manager | `backend/services/core/risk_manager.py` | Position limits | Working |
| Circuit Breaker | `backend/services/core/circuit_breaker.py` | Emergency halt | Working |
| Fee Calculator | `backend/services/core/fee_calculator.py` | Fee calculations | Working |
| Kelly Sizing | `backend/services/core/kelly_sizing.py` | Position sizing | Working |
| Performance Tracker | `backend/services/core/performance_tracker.py` | P&L metrics | Working |
| Alert Service | `backend/services/core/alert_service.py` | Real-time alerts | Working |
| Backtest Engine | `backend/services/core/backtest_engine.py` | Historical testing | Untested |

### Services - Strategies

| Module | Path | Purpose | Status |
|--------|------|---------|--------|
| Base Strategy | `backend/services/core/base_strategy.py` | Strategy ABC | Working |
| Weather Strategy | `backend/services/strategies/weather_strategy.py` | Weather bracket arb | **BUG: Fee not integrated** |
| BTC Arb Strategy | `backend/services/strategies/btc_arb_strategy.py` | BTC range/threshold | Working |
| BTC Directional | `backend/services/strategies/btc_directional_strategy.py` | BTC directional | Working |

### Services - Analysis

| Module | Path | Purpose | Status |
|--------|------|---------|--------|
| Arbitrage Calculator | `backend/services/analysis/arbitrage_calculator.py` | Enhanced arb detection | Working |
| Probability Engine | `backend/services/analysis/probability_engine.py` | Weather probability | Working |
| Prediction Engine V2 | `backend/services/analysis/prediction_engine_v2.py` | Fee-aware predictions | Working |
| Position Calculator | `backend/services/analysis/position_calculator.py` | Portfolio calcs | Working |

### Services - External Clients

| Module | Path | Purpose | Status |
|--------|------|---------|--------|
| Kalshi Client | `backend/services/kalshi_client.py` | Kalshi REST API | Working |
| NWS Client | `backend/services/nws/client.py` | Weather forecasts | Working |
| Spot Price Client | `backend/services/spot_price_client.py` | BTC price (free APIs) | Working |

### Services - Scanners

| Module | Path | Purpose | Status |
|--------|------|---------|--------|
| BTC Arb Scanner | `backend/services/btc_arb_scanner.py` | 2-second interval | Working |
| Weather Arb Scanner | `backend/services/weather_arb_scanner.py` | 30-second interval | Working |
| Scanner DB | `backend/services/scanner_db.py` | Scanner result storage | Working |

### Services - Support

| Module | Path | Purpose | Status |
|--------|------|---------|--------|
| Paper Trading | `backend/services/paper_trading.py` | Simulation engine | Working |
| Trade Executor | `backend/services/trade_executor.py` | Paper/live router | Working |
| Portfolio Service | `backend/services/portfolio_service.py` | Portfolio summary | Working |
| Watchlist Service | `backend/services/watchlist_service.py` | Saved markets | Working |
| Reconciliation | `backend/services/reconciliation/reconciler.py` | Position sync | Untested |

### Data Models

| Module | Path | Purpose | Status |
|--------|------|---------|--------|
| Kalshi Models | `backend/models/kalshi_models.py` | API data models | **BUG: bracket_label()** |
| NWS Models | `backend/models/nws_models.py` | Weather models | Working |
| Execution Models | `backend/models/execution_models.py` | Trade models | Working |
| Types | `backend/models/types.py` | Enums, TypedDicts | Working |

### Frontend Components

| Module | Path | Purpose |
|--------|------|---------|
| ArbitrageHub | `frontend/src/components/arbitrage/ArbitrageHub.tsx` | Main arbitrage UI |
| WeatherArbitrageSection | `frontend/src/components/arbitrage/WeatherArbitrageSection.tsx` | Weather scanner |
| CryptoArbitrageSection | `frontend/src/components/arbitrage/CryptoArbitrageSection.tsx` | BTC scanner |
| ExecutionPanel | `frontend/src/components/arbitrage/ExecutionPanel.tsx` | Trade execution |
| RiskDashboard | `frontend/src/components/arbitrage/RiskDashboard.tsx` | Risk monitoring |
| PortfolioTab | `frontend/src/components/portfolio/PortfolioTab.tsx` | Positions |
| AutoTraderTab | `frontend/src/components/autotrader/AutoTraderTab.tsx` | Auto-trading |

## File Tree (Condensed)

```
kalshi-bc-arb/
├── backend/
│   ├── main.py                          # FastAPI entry (331 lines)
│   ├── api/
│   │   ├── routes.py                    # REST endpoints (1,747 lines)
│   │   ├── prediction_routes.py         # Weather predictions (545 lines)
│   │   ├── websocket_routes.py          # WebSocket handlers (318 lines)
│   │   └── schemas.py                   # API schemas (284 lines)
│   ├── models/
│   │   ├── kalshi_models.py             # Kalshi data models (456 lines)
│   │   ├── nws_models.py                # Weather models (281 lines)
│   │   ├── execution_models.py          # Trade models (136 lines)
│   │   └── types.py                     # Enums/TypedDicts (141 lines)
│   ├── services/
│   │   ├── core/                        # Trading infrastructure (14 files, ~6,500 lines)
│   │   │   ├── strategy_orchestrator.py # Main engine (626 lines)
│   │   │   ├── execution_gateway.py     # Trade entry point (1,208 lines)
│   │   │   ├── position_manager.py      # Position tracking (597 lines)
│   │   │   ├── fee_calculator.py        # Fee calcs (602 lines)
│   │   │   ├── batch_executor.py        # Multi-leg exec (421 lines)
│   │   │   ├── risk_manager.py          # Risk limits (330 lines)
│   │   │   ├── circuit_breaker.py       # Emergency halt (303 lines)
│   │   │   ├── signal_manager.py        # Signal lifecycle (374 lines)
│   │   │   ├── kelly_sizing.py          # Position sizing (248 lines)
│   │   │   ├── performance_tracker.py   # P&L metrics (454 lines)
│   │   │   ├── alert_service.py         # Alerts (350 lines)
│   │   │   ├── backtest_engine.py       # Backtesting (511 lines)
│   │   │   └── base_strategy.py         # Strategy ABC (285 lines)
│   │   ├── strategies/                  # Strategy implementations
│   │   │   ├── weather_strategy.py      # Weather arb (631 lines)
│   │   │   ├── btc_arb_strategy.py      # BTC arb (267 lines)
│   │   │   └── btc_directional_strategy.py # BTC directional (490 lines)
│   │   ├── analysis/                    # Analysis engines
│   │   │   ├── arbitrage_calculator.py  # Arb detection (630 lines)
│   │   │   ├── probability_engine.py    # Weather prob (402 lines)
│   │   │   ├── prediction_engine_v2.py  # Fee-aware (560 lines)
│   │   │   └── position_calculator.py   # Portfolio (358 lines)
│   │   ├── nws/                         # Weather service
│   │   │   ├── client.py                # NWS client
│   │   │   └── config.py                # Grid points
│   │   ├── websocket/                   # Real-time data
│   │   │   ├── manager.py               # WS management
│   │   │   ├── data_sync.py             # Data sync
│   │   │   └── orderbook_builder.py     # Orderbook
│   │   ├── reconciliation/
│   │   │   └── reconciler.py            # Position sync
│   │   ├── kalshi_client.py             # Kalshi API (302 lines)
│   │   ├── paper_trading.py             # Simulation (305 lines)
│   │   ├── btc_arb_scanner.py           # BTC scanner (719 lines)
│   │   ├── weather_arb_scanner.py       # Weather scanner (381 lines)
│   │   └── ...
│   ├── database/
│   │   ├── connection.py                # SQLite manager
│   │   └── schema.sql                   # Table defs
│   ├── config/
│   │   ├── __init__.py                  # Settings
│   │   └── locations/                   # Weather configs
│   └── utils/
│       └── kalshi_auth.py               # RSA-PSS auth
├── frontend/
│   ├── src/
│   │   ├── App.tsx                      # Root component
│   │   ├── components/
│   │   │   ├── arbitrage/               # Arbitrage UI (11 files)
│   │   │   ├── portfolio/               # Portfolio
│   │   │   ├── trading/                 # Trading UI
│   │   │   └── ...
│   │   ├── stores/                      # Zustand stores
│   │   ├── hooks/                       # React hooks
│   │   └── services/api.ts              # Backend client
│   └── vite.config.ts
├── context/                             # Documentation
│   ├── INDEX.md                         # This file
│   ├── API.md                           # API reference
│   └── SCHEMAS.md                       # Data schemas
├── .claude/CLAUDE.md                    # AI assistant context
├── start.bat                            # Launch all services
└── test_core_components.py              # Core tests
```

## Key Statistics

| Metric | Count |
|--------|-------|
| Python Files (backend) | 78 |
| TypeScript/React Files | 43 |
| Python Lines | ~77,500 |
| React/TS Lines | ~6,139 |
| REST Endpoints | 72 |
| Core Infrastructure Files | 14 |
| Strategy Implementations | 3 |

## Known Issues

| Issue | Location | Impact | Priority |
|-------|----------|--------|----------|
| Fee not integrated in edge calc | `weather_strategy.py:333-338` | Shows inflated edge (2.04% vs actual -6.54%) | CRITICAL |
| No partial fill rollback | `batch_executor.py:255-290` | Unhedged positions on partial fills | CRITICAL |
| Cache stale on partial fills | `execution_gateway.py:294-297` | 30s stale data after partial fills | HIGH |
| Bracket label off-by-1 | `kalshi_models.py:265-273` | Wrong display for open-ended brackets | MEDIUM |

## Dependencies

### Critical Path
```
StrategyOrchestrator
  → WeatherStrategy/BTCStrategy
    → ExecutionGateway
      → BatchExecutor
        → KalshiClient (live) / PaperTrading (paper)
          → PositionManager
            → RiskManager + CircuitBreaker
```

### Fee Integration Path (BROKEN)
```
WeatherStrategy._check_bracket_arbitrage()
  ✗ MISSING: FeeCalculator.calculate_multi_leg()
  → TradingSignal with inflated edge_percent
```
