# 🎯 Kalshi Arbitrage Trading System - Ralph Cleanup Mission

## Project Identity
**Name:** Kalshi Bracket Arbitrage Scanner  
**Mission:** Exploit pricing inefficiencies in prediction markets  
**Current State:** BROKEN - Multiple bugs + severe code bloat  
**Target State:** Lean, working, ready for paper trading validation

## Tech Stack
- **Backend:** Python 3.10+ / FastAPI (port 8001)
- **Frontend:** React 18 / TypeScript / Vite (port 5173)
- **Database:** SQLite (paper trading simulation)
- **External APIs:** Kalshi REST/WebSocket, National Weather Service
- **Auth:** RSA-PSS cryptographic signing

## Directory Structure (Target - After Cleanup)
```
kalshi-arb/
├── backend/
│   ├── main.py                    # FastAPI app + lifespan
│   ├── api/
│   │   ├── routes.py              # All REST endpoints
│   │   └── websocket.py           # WebSocket handlers
│   ├── config/
│   │   └── __init__.py            # Pydantic Settings (SINGLE source)
│   ├── database/
│   │   ├── connection.py
│   │   └── schema.sql
│   ├── models/                    # Pydantic models only
│   ├── services/
│   │   ├── kalshi_client.py       # Kalshi API wrapper
│   │   ├── paper_trading.py       # Paper trade simulation
│   │   ├── nws_client.py          # Weather forecasts
│   │   └── core/                  # ⭐ THE ONLY trading infrastructure
│   │       ├── fee_calculator.py
│   │       ├── circuit_breaker.py
│   │       ├── risk_manager.py
│   │       ├── position_manager.py
│   │       ├── execution_gateway.py
│   │       └── strategy_orchestrator.py
│   └── strategies/                # BaseStrategy implementations
│       ├── weather_strategy.py
│       ├── btc_arb_strategy.py
│       └── btc_directional_strategy.py
├── frontend/
│   └── src/
│       ├── components/
│       │   └── arbitrage/
│       │       └── WeatherArbitrageSection.tsx  # FIX BRACKET BUG HERE
│       ├── hooks/
│       ├── stores/
│       └── types/
├── start.bat                      # Launches ONLY 2 terminals now
└── .env                           # Credentials (NEVER commit)
```

## 🚨 CRITICAL CONSTRAINTS

### 1. SAFETY FIRST - This is a Trading System!
- **NEVER** auto-enable live trading
- **ALWAYS** default to paper mode
- **NEVER** commit API keys or private keys
- **ALWAYS** route trades through ExecutionGateway

### 2. Kalshi Position Rule (WILL LOSE MONEY IF IGNORED)
```
⚠️ Kalshi does NOT allow holding both YES and NO on the same market.
   Buying YES auto-sells any NO position (and vice versa).
   Arbitrage strategies must use EITHER yes OR no per bracket, never both.
```

### 3. Fee Calculation (MUST BE ACCURATE)
```python
# Kalshi fee formula - USE THIS EVERYWHERE
fee = ceil(0.07 * contracts * price * (1 - price))
# Example: 10 contracts at 45¢ = ceil(0.07 * 10 * 0.45 * 0.55) = ceil(0.17325) = 1¢
```

### 4. Data Flow Rule
```
Kalshi API → Backend (pass-through) → Frontend (display only)
            ↑                         ↑
         NO transforming          NO calculating
         bracket labels           bracket labels
```

## Current Bugs (Priority Order)

### 🔴 P0: Bracket Label Bug (CRITICAL)
**Symptom:** Weather brackets show +2°F offset vs Kalshi website
- Scanner shows: ≤48°F, 49-50°F, 51-52°F, ≥57°F
- Kalshi shows:  46° or below, 47-48°, 49-50°, 55° or above

**Root Cause:** Backend generates labels from forecast instead of using Kalshi's `floor_strike`/`cap_strike`

**Fix Location:** 
- Backend: `weather_arb_scanner.py` → `_analyze_series()`
- Frontend: `WeatherArbitrageSection.tsx` → `getBracketLabel()`

### 🔴 P0: Startup Crash
**Symptom:** `TypeError: BTCArbitrageEngine.__init__() missing required arguments`
**Fix Location:** `routes.py` singleton pattern + `main.py` initialization

### 🟡 P1: Project Bloat
**Symptom:** 45+ Python files, many duplicates, 3 competing trading engines
**Target:** ~25 Python files, zero duplicates, 1 orchestrator

## Files to DELETE (Bloat Removal)
```
# Duplicate fee calculators (keep core/)
backend/services/fee_calculator.py
backend/services/analysis/fee_calculator.py

# Duplicate circuit breakers (keep core/)
backend/services/risk/circuit_breaker.py

# Competing engines (keep strategy_orchestrator + strategies/)
backend/services/btc_arb_engine.py
backend/services/auto_trader.py
backend/services/edge_detector.py

# Scanner processes (integrate into main.py)
run_scanners.py
run_logs.py
backend/services/scanner_service.py
backend/services/scanner_db.py

# Unused/empty modules
backend/services/execution/  (entire directory)
backend/services/risk/       (entire directory after CB move)
backend/services/websocket/  (merge into api/websocket.py)
```

## Files to KEEP and ENHANCE
```
backend/services/core/fee_calculator.py      # Single fee calculator
backend/services/core/circuit_breaker.py     # Single circuit breaker
backend/services/core/execution_gateway.py   # ALL trades go through here
backend/services/core/strategy_orchestrator.py
backend/services/kalshi_client.py
backend/services/paper_trading.py
backend/strategies/*.py
```

## Testing Commands
```bash
# After each change, verify:
cd backend && python -c "from main import app; print('✅ Backend imports OK')"
cd frontend && npm run build && echo "✅ Frontend builds OK"

# Full integration test:
python test_integration_startup.py
```

## Ralph's Personality for This Mission
Channel your inner Ralph Wiggum:
- "I'm helping!" (delete duplicate files)
- "My cat's breath smells like cat food" (find stale data bugs)  
- "I bent my Wookiee" (fix broken imports after deletions)
- "I picked one! I picked one!" (choose the RIGHT fee_calculator.py)

## Success Criteria
1. ✅ Server starts without errors
2. ✅ Weather brackets match Kalshi.com exactly
3. ✅ Python file count < 30
4. ✅ Zero duplicate services
5. ✅ All trades route through ExecutionGateway
6. ✅ Paper trading works end-to-end
