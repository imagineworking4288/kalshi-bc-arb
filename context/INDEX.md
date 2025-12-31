# Kalshi Arbitrage Scanner

Automated trading bot that detects and executes arbitrage opportunities on Kalshi prediction markets. Provides real-time monitoring, paper trading simulation, and a web dashboard for tracking profitable bracket-vs-threshold arbitrage trades.

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
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   External      │
│   React/TS      │◄──►│   FastAPI       │◄──►│   APIs          │
│   :5173         │    │   :8000         │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                      │                      │
        ├─ App.tsx            ├─ main.py             ├─ Kalshi API
        ├─ Stores             ├─ API Routes          ├─ CoinGecko
        ├─ Components         ├─ Services            └─ CoinLore
        └─ Services           ├─ Database
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
| frontend/components/analytics | frontend/src/components/analytics/ | P&L analytics display |
| frontend/components/common | frontend/src/components/common/ | Reusable UI components |
| frontend/components/layout | frontend/src/components/layout/ | Header and navigation |
| frontend/components/opportunities | frontend/src/components/opportunities/ | Arbitrage opportunity display and execution |
| frontend/components/trading | frontend/src/components/trading/ | Trading mode and position management |
| frontend/services | frontend/src/services/ | Backend API client |
| frontend/stores | frontend/src/stores/ | Zustand state management |
| frontend/types | frontend/src/types/ | TypeScript type definitions |
| frontend/utils | frontend/src/utils/ | Formatting utilities |

## Entry Points

| File | Command | When to use |
|------|---------|-------------|
| backend/main.py | `uvicorn backend.main:app --reload` | Start FastAPI backend server |
| frontend/src/main.tsx | `npm run dev` (in frontend/) | Start React development server |
| docker-compose.yml | `docker-compose up` | Run full stack in containers |

## File Tree

| File | Description |
|------|-------------|
| .env | Environment variables for API keys |
| .env.example | Template for environment setup |
| .gitignore | Git ignore patterns |
| README.md | Project documentation and setup |
| docker-compose.yml | Docker container orchestration config |
| backend/main.py | FastAPI app entry point |
| backend/config.py | Settings from environment variables |
| backend/requirements.txt | Python package dependencies |
| diagnose_kalshi.py | Legacy Kalshi API test script |
| diagnose_kalshi_v2.py | Updated API diagnostic with auth tests |
| start.bat | Windows batch script to start servers |
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
| backend/services/spot_price_client.py | Free API BTC price client (CoinGecko/CoinLore) |
| backend/services/trade_executor.py | Routes trades to paper or live |
| backend/utils/__init__.py | Utils module exports |
| backend/utils/kalshi_auth.py | RSA-PSS signature authentication |
| data/.gitkeep | Placeholder for SQLite database |
| keys/.gitkeep | Placeholder for API key files |
| keys/kalshi-private-key.pem | RSA private key for Kalshi |
| frontend/index.html | Main HTML template |
| frontend/package.json | NPM dependencies and scripts |
| frontend/postcss.config.js | PostCSS config for Tailwind |
| frontend/tailwind.config.js | Tailwind CSS configuration |
| frontend/tsconfig.json | TypeScript compiler options |
| frontend/tsconfig.node.json | Node TypeScript config |
| frontend/vite.config.ts | Vite bundler configuration |
| frontend/src/App.tsx | Root React component with tabs |
| frontend/src/index.css | Global Tailwind CSS styles |
| frontend/src/main.tsx | React DOM entry point |
| frontend/src/vite-env.d.ts | Vite type definitions |
| frontend/src/components/analytics/AnalyticsTab.tsx | P&L summary dashboard |
| frontend/src/components/common/Modal.tsx | Reusable modal dialog |
| frontend/src/components/layout/Header.tsx | App header with balance |
| frontend/src/components/layout/TabNav.tsx | Tab navigation component |
| frontend/src/components/opportunities/ExecuteModal.tsx | Trade execution confirmation modal |
| frontend/src/components/opportunities/OpportunitiesTab.tsx | Arbitrage opportunities list |
| frontend/src/components/opportunities/OpportunityCard.tsx | Single opportunity display |
| frontend/src/components/trading/ModeBanner.tsx | Paper/live mode status banner |
| frontend/src/components/trading/ModeToggle.tsx | Paper/live mode switcher |
| frontend/src/components/trading/PositionList.tsx | Open positions display |
| frontend/src/components/trading/TradeHistory.tsx | Historical trades list |
| frontend/src/components/trading/TradingTab.tsx | Trading dashboard view |
| frontend/src/services/api.ts | Backend HTTP API client |
| frontend/src/stores/opportunityStore.ts | Opportunities Zustand store |
| frontend/src/stores/tradingStore.ts | Trading state Zustand store |
| frontend/src/types/index.ts | TypeScript interfaces |
| frontend/src/utils/format.ts | Currency and time formatters |
