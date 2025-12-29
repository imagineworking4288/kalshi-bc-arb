# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Opportunity │  │   Trading    │  │     Analytics          │  │
│  │    List     │  │    Modal     │  │     Dashboard          │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
│                            │                                      │
│                   ┌────────┴────────┐                            │
│                   │   Zustand Stores │                           │
│                   └────────┬────────┘                            │
│                            │                                      │
│         ┌──────────────────┼──────────────────┐                  │
│         │                  │                  │                  │
│    ┌────┴────┐      ┌─────┴─────┐     ┌─────┴─────┐            │
│    │   API   │      │ WebSocket │     │  Alerts   │            │
│    │ Service │      │  Service  │     │  Service  │            │
│    └────┬────┘      └─────┬─────┘     └───────────┘            │
└─────────┼─────────────────┼────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Backend (FastAPI)                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      API Routes                           │  │
│  │  /opportunities  /trade  /analytics  /history            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                      │
│  ┌─────────────────────────┼─────────────────────────────────┐  │
│  │                    Services Layer                          │  │
│  │                                                            │  │
│  │  ┌───────────────┐  ┌──────────────┐  ┌────────────────┐ │  │
│  │  │ Market Service│  │ Arb Engine   │  │ Trade Executor │ │  │
│  │  └───────┬───────┘  └──────────────┘  └────────────────┘ │  │
│  │          │                                                 │  │
│  │  ┌───────┴───────┐  ┌──────────────┐  ┌────────────────┐ │  │
│  │  │ Kalshi Client │  │ Fee Calc     │  │ Position Track │ │  │
│  │  └───────────────┘  └──────────────┘  └────────────────┘ │  │
│  │                                                            │  │
│  │  ┌───────────────┐  ┌──────────────┐  ┌────────────────┐ │  │
│  │  │CF Benchmarks  │  │ Opp Logger   │  │ Analytics Svc  │ │  │
│  │  └───────────────┘  └──────────────┘  └────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            │                                      │
│  ┌─────────────────────────┴─────────────────────────────────┐  │
│  │                        Database                            │  │
│  │                       (SQLite)                             │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
          │                           │
          ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐
│    Kalshi API       │    │   CF Benchmarks     │
│  (REST + WebSocket) │    │      (REST)         │
└─────────────────────┘    └─────────────────────┘
```

## Core Concepts

### Arbitrage Detection

The system detects arbitrage opportunities between two types of Kalshi markets:

1. **Threshold Markets**: "Will BTC be above $95,000?"
2. **Bracket Markets**: "Will BTC be between $95,000 and $97,500?"

**Mathematical Relationship:**
For an "above T" threshold, the price should equal the sum of all bracket prices above T:

```
P(above T) = Σ P(bracket) for all brackets where low_bound >= T
```

When this relationship doesn't hold, an arbitrage opportunity exists.

### Components

#### Frontend

- **React 18** with TypeScript
- **Zustand** for state management
- **Tailwind CSS** for styling
- **Recharts** for analytics visualizations

#### Backend

- **FastAPI** for REST API and WebSocket
- **SQLite** for data persistence
- **httpx** for async HTTP requests
- **aiosqlite** for async database operations

### Data Flow

1. **Market Fetching**
   - `MarketService` fetches markets from Kalshi
   - `MarketClassifier` categorizes as threshold or bracket
   - Markets grouped by asset + settlement time

2. **Opportunity Detection**
   - `ArbitrageEngine` analyzes market groups
   - Calculates implied prices from brackets
   - Identifies divergences above profit threshold
   - Scores opportunities by profit, liquidity, timing

3. **Trade Execution**
   - `TradeExecutor` builds order legs
   - Executes all legs concurrently
   - `PositionTracker` records trades

4. **Analytics**
   - `OpportunityLogger` stores all detections
   - `AnalyticsService` provides aggregations
   - Historical data for pattern analysis

### Fee Calculation

Kalshi uses this fee formula:
```
Fee = ceil(0.07 × contracts × price × (1 - price))
```

This is implemented in `fee_calculator.py` and applied to all profit calculations.

### Position Sizing

The system provides several sizing strategies:
- **Conservative**: 2% of balance
- **Moderate**: 5% of balance
- **Aggressive**: 10% of balance
- **Kelly Criterion**: Optimal sizing based on edge
- **Max Liquidity**: Limited by order book depth

## Security Considerations

1. **API Credentials**
   - Private key stored in `keys/` directory
   - Never committed to version control
   - RSA signing for all API requests

2. **Environment Isolation**
   - Clear separation of demo/production
   - Confirmation dialog for production mode
   - Environment badge always visible

3. **Risk Limits**
   - Configurable max position per market
   - Max total exposure limit
   - Max single trade limit
   - Max daily loss limit
