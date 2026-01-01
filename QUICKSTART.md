# Quick Start Guide - Kalshi Trading Platform

## First Time Setup

1. **Install dependencies** (if not already done):
   ```bash
   cd frontend
   npm install
   cd ..
   ```

2. **Verify Python virtual environment**:
   ```bash
   # Should exist from previous setup
   backend\venv\Scripts\activate
   ```

## Launch Platform

Simply run:
```bash
start.bat
```

This opens **4 terminal windows**:

### Terminal 1: Frontend (React)
```
Kalshi Frontend
http://localhost:5173
```
- Tab navigation: Arbitrage, Portfolio, Trade, etc.
- Real-time updates from API

### Terminal 2: Backend API (FastAPI)
```
Kalshi API
http://localhost:8001
http://localhost:8001/docs  (Swagger UI)
```
- REST API serving data
- Reads from scanner database
- Fast, non-blocking

### Terminal 3: Scanners
```
Kalshi Scanners
- BTC: Every 2s
- Weather: Every 30s (14 series)
```
- Writes to `data/scanner_results.db`
- Independent of API

### Terminal 4: Logs
```
Kalshi Logs
Colored, real-time log viewer
```
- All services log here
- Color-coded by source

## Stop Platform

```bash
stop.bat
```

Or just close the launcher terminal window.

---

## Quick API Tests

### Check Scanner Status
```bash
curl http://localhost:8001/scanners/status
```

### BTC Arbitrage
```bash
curl http://localhost:8001/btc-arb/status
```

### Weather Arbitrage
```bash
curl http://localhost:8001/weather-arb/status
```

### Weather by City
```bash
curl http://localhost:8001/weather-arb/city/NYC
```

### Recent Logs
```bash
curl "http://localhost:8001/logs/recent?lines=50&source=weather"
```

---

## Architecture Highlights

**Scanners Run Independently**
- No blocking of API requests
- Write results to SQLite
- API reads instantly from database

**Weather Coverage**
- 7 cities: NYC, LAX, CHI, MIA, DEN, AUS, PHL
- 2 types each: HIGH and LOW temperature
- **14 total series** scanned every 30s

**BTC Coverage**
- KXBTC (ranges) + KXBTCD (thresholds)
- Settlement time matching
- Scanned every 2s

**Logging**
- Centralized across all services
- Rotating file handlers
- Color-coded console output
- Filterable in real-time

---

## Troubleshooting

### Port already in use
If port 8001 is busy:
```bash
netstat -ano | findstr :8001
taskkill /PID <pid> /F
```

### Scanner not finding opportunities
1. Check logs in Terminal 4
2. Verify Kalshi API credentials in `.env`
3. Check scanner status: `curl http://localhost:8001/scanners/status`

### Frontend not loading
1. Verify `npm install` completed in `frontend/`
2. Check Terminal 1 for errors
3. Try: `cd frontend && npm run dev`

### Logs not showing
1. Verify `logs/` directory exists (created automatically)
2. Check Terminal 3 - scanners create log files
3. Try: `python run_logs.py --file all`

---

## What to Watch

In **Terminal 4** (Logs):
- `[btc_arb]` - BTC scanner activity (yellow)
- `[weather_arb]` - Weather scanner activity (cyan)
- `[nws_client]` - NWS forecast fetches (cyan)
- `[api]` - API requests (magenta)
- `[ERROR]` - Any errors (red)

Look for:
- **[OK] ARB** - Arbitrage opportunity found
- **[HOT] Near** - Near-miss (within 5¢)
- **[SCAN] Scanned** - Scan completion summary

---

## Next Steps

1. **Open frontend**: http://localhost:5173
2. **View opportunities**: Click " Arbitrage" tab
3. **Check logs**: Watch Terminal 4 for scanner activity
4. **Test API**: http://localhost:8001/docs

Enjoy trading! 
