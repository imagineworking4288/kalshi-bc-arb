# 🎯 Kalshi Visual Bug Fixes

## Mission
Fix the 3 critical visual bugs that make the app unusable.

## Current State (BROKEN)

### Weather Brackets
❌ Labels are 3-5°F LOWER than Kalshi.com
- Your app: "39° or below" → Kalshi: "42° or below"
- Your app: "41-42°F" → Kalshi: "45-46°"
- Root cause: Not using floor_strike/cap_strike from API

### Bitcoin Scanner
❌ Shows all zeros, scanner STOPPED
- Scans: 0, Ranges: 0, Thresholds: 0
- Scanner never starts or data not returned
- Root cause: API may return deprecation or scanner not initialized

### WebSocket
❌ No real-time updates
- Must manually refresh
- No LIVE indicator
- Root cause: WebSocket not connected

## Tech Stack
- Frontend: React/TypeScript (port 5173)
- Backend: FastAPI/Python (port 8001)
- Data: Kalshi API, NWS API

## Priority Order
1. **Weather brackets** - Highest impact, likely easiest fix
2. **Bitcoin scanner** - Core feature, medium effort
3. **WebSocket** - Nice to have, can defer

## Key Files

### Weather Brackets
```
frontend/src/components/arbitrage/WeatherArbitrageSection.tsx
```
Look for: getBracketLabel, formatBracket, or any temperature parsing

### Bitcoin Scanner
```
backend/api/routes.py - Check /api/btc-arb/status
backend/main.py - Check scanner initialization
backend/services/btc_arb_scanner.py - Check scan logic
```

### WebSocket
```
backend/main.py or backend/api/websocket.py
frontend/src/hooks/useWebSocket.ts (if exists)
```

## Success = Match Kalshi.com
The app labels must **exactly match** what Kalshi.com shows.
No offsets, no approximations, exact matches.
