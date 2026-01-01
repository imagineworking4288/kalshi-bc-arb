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
| backend/utils | backend/utils/ | Kalshi RSA-PSS authentication |
| backend/config | backend/config/ | Settings and location configurations |
| frontend/components/analytics | frontend/src/components/analytics/ | P&L analytics display |
| frontend/components/common | frontend/src/components/common/ | Reusable UI components |
| frontend/components/layout | frontend/src/components/layout/ | Header and navigation |
| frontend/components/arbitrage | frontend/src/components/arbitrage/ | Multi-market arbitrage hub with crypto and weather sections |
| frontend/components/opportunities | frontend/src/components/opportunities/ | Arbitrage opportunity display and execution |
| frontend/components/portfolio | frontend/src/components/portfolio/ | Portfolio overview and position tracking |
| frontend/components/trade | frontend/src/components/trade/ | Manual trading interface |
| frontend/components/trading | frontend/src/components/trading/ | Trading mode and position management |
| frontend/components/watchlist | frontend/src/components/watchlist/ | Saved markets management |
| frontend/components/autotrader | frontend/src/components/autotrader/ | Automated trading and edge detection |
| frontend/components/btcarb | frontend/src/components/btcarb/ | Legacy BTC arbitrage (replaced by arbitrage hub) |
| frontend/hooks | frontend/src/hooks/ | Custom React hooks |
| frontend/services | frontend/src/services/ | Backend API client |
| frontend/stores | frontend/src/stores/ | Zustand state management |
| frontend/types | frontend/src/types/ | TypeScript type definitions |
| frontend/utils | frontend/src/utils/ | Formatting utilities |

## Entry Points

| File | Command | When to use |
|------|---------|-------------|
| backend/main.py | `uvicorn backend.main:app --reload` | Start FastAPI backend server |
| frontend/src/main.tsx | `npm run dev` (in frontend/) | Start React development server |
| run_scanners.py | `python run_scanners.py` | Run weather and BTC scanners independently |
| run_logs.py | `python run_logs.py` | Run colored log viewer with filtering |
| start.bat | `start.bat` | Launch all 4 services in Windows Terminal tabs |
| stop.bat | `stop.bat` | Stop all platform services |
| docker-compose.yml | `docker-compose up` | Run full stack in containers |

## File Tree

| File | Description |
|------|-------------|
| README.md | Project documentation and setup |
| MVP_IMPLEMENTATION.md | Implementation guide and roadmap |
| .claude/settings.local.json | Claude configuration settings |
| backend/main.py | FastAPI app entry point |
| backend/config.py | Legacy settings (replaced by config module) |
| backend/config/__init__.py | Pydantic settings with location configs |
| backend/config/fees.py | Kalshi fee calculation utilities |
| backend/config/locations/__init__.py | Location module exports |
| backend/config/locations/base.py | LocationConfig dataclass with forecast adjustments |
| backend/config/locations/registry.py | Weather location definitions (7 cities) |
| diagnose_kalshi.py | Legacy Kalshi API test script |
| diagnose_kalshi_v2.py | Updated API diagnostic with auth tests |
| package-lock.json | NPM dependency lock file |
| start.bat | Windows batch 4-terminal launcher script |
| stop.bat | Stop all Kalshi platform services |
| run_scanners.py | Scanner service entry point |
| run_logs.py | Log viewer entry point |
| backend/api/__init__.py | API module exports |
| backend/api/routes.py | REST API endpoint handlers |
| backend/api/websocket.py | WebSocket connection manager |
| backend/database/__init__.py | Database module exports |
| backend/database/connection.py | SQLite async connection manager |
| backend/database/schema.sql | Table definitions for paper trading |
| backend/models/__init__.py | Models module exports |
| backend/models/schemas.py | Pydantic request models |
| backend/services/__init__.py | Services module exports all classes |
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
| backend/utils/__init__.py | Utils module exports |
| backend/utils/kalshi_auth.py | RSA-PSS signature authentication |
| backend/utils/logger.py | Logging system with activity buffer |
| keys/kalshi-private-key.pem | RSA private key for Kalshi |
| frontend/index.html | Main HTML template |
| frontend/package.json | NPM dependencies and scripts |
| frontend/postcss.config.js | PostCSS config for Tailwind |
| frontend/tailwind.config.js | Tailwind CSS configuration |
| frontend/tsconfig.json | TypeScript compiler options |
| frontend/tsconfig.node.json | Node TypeScript config |
| frontend/vite.config.ts | Vite bundler configuration |
| frontend/src/App.tsx | Root React component with arbitrage hub navigation |
| frontend/src/index.css | Global Tailwind CSS styles |
| frontend/src/main.tsx | React DOM entry point |
| frontend/src/vite-env.d.ts | Vite type definitions |
| frontend/src/components/analytics/AnalyticsTab.tsx | P&L summary dashboard |
| frontend/src/components/arbitrage/ArbitrageHub.tsx | Main arbitrage hub with sub-navigation |
| frontend/src/components/arbitrage/CryptoArbitrageSection.tsx | Crypto arbitrage scanner with card-based UI |
| frontend/src/components/arbitrage/WeatherArbitrageSection.tsx | Weather arbitrage scanner placeholder |
| frontend/src/components/arbitrage/shared/StatsBar.tsx | Reusable statistics display component |
| frontend/src/components/arbitrage/shared/ConfigPanel.tsx | Reusable configuration controls component |
| frontend/src/components/arbitrage/shared/OpportunityTable.tsx | Reusable opportunity table component |
| frontend/src/components/common/Modal.tsx | Reusable modal dialog |
| frontend/src/components/layout/Header.tsx | App header with balance |
| frontend/src/components/layout/TabNav.tsx | Tab navigation component |
| frontend/src/components/opportunities/ExecuteModal.tsx | Trade execution confirmation modal |
| frontend/src/components/opportunities/OpportunitiesTab.tsx | Arbitrage opportunities list |
| frontend/src/components/opportunities/OpportunityCard.tsx | Single opportunity display |
| frontend/src/components/portfolio/PortfolioTab.tsx | Portfolio overview with positions and orders |
| frontend/src/components/trade/TradeCard.tsx | Manual trading market card interface |
| frontend/src/components/trade/TradeTab.tsx | Manual trading tab wrapper |
| frontend/src/components/trading/ModeBanner.tsx | Paper/live mode status banner |
| frontend/src/components/trading/ModeToggle.tsx | Paper/live mode switcher |
| frontend/src/components/trading/PositionList.tsx | Open positions display |
| frontend/src/components/trading/TradeHistory.tsx | Historical trades list |
| frontend/src/components/trading/TradingTab.tsx | Trading dashboard view |
| frontend/src/components/watchlist/WatchlistTab.tsx | Saved markets with live prices |
| frontend/src/components/autotrader/AutoTraderTab.tsx | Auto-trading control panel and signal monitoring |
| frontend/src/components/btcarb/BTCArbitrageTab.tsx | BTC arbitrage monitoring with near-misses table and opportunity tracking |
| frontend/src/hooks/useSpotPrice.ts | Live BTC price polling hook |
| frontend/src/services/api.ts | Backend HTTP API client |
| frontend/src/stores/opportunityStore.ts | Opportunities Zustand store |
| frontend/src/stores/tradingStore.ts | Trading state Zustand store |
| frontend/src/types/index.ts | TypeScript interfaces |
| frontend/src/utils/format.ts | Currency and time formatters |
