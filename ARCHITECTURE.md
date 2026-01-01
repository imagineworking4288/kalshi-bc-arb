# Kalshi Trading Platform - 4-Terminal Architecture

## Overview

The platform now uses a **4-terminal architecture** for optimal performance and separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Terminal 1    │    │   Terminal 2    │    │   Terminal 3    │
│   Frontend      │◄──►│   Backend API   │◄──►│   Scanners      │
│   React/Vite    │    │   FastAPI       │    │   BTC/Weather   │
│   :5173         │    │   :8001         │    │   SQLite Write  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                             │                        │
                             │                        ▼
                             │                 ┌─────────────────┐
                             │                 │ scanner_results │
                             └────────────────►│    .db          │
                                   (reads)     │                 │
                                               └─────────────────┘
                                                        │
                        ┌───────────────────────────────┘
                        ▼
                 ┌─────────────────┐
                 │   Terminal 4    │
                 │   Log Viewer    │
                 │   Tail logs/    │
                 │   colored       │
                 └─────────────────┘
```

## Why This Architecture?

**Problem Solved**: Previous architecture had scanners blocking API requests during scans.

**Solution**:
- **Terminal 3** runs scanners independently, writing results to SQLite
- **Terminal 2** API reads from SQLite instantly (no blocking)
- **Terminal 4** provides centralized log monitoring

## Launch

```bash
start.bat
```

This opens 4 terminals:
1. **Frontend** - React UI
2. **API** - FastAPI server
3. **Scanners** - BTC (2s) + Weather (30s)
4. **Logs** - Colored log viewer

## Stop

```bash
stop.bat
```

Closes all 4 terminals.

---

## Scanner Details

### BTC Arbitrage Scanner
- **Frequency**: Every 2 seconds
- **Markets**: KXBTC (ranges) + KXBTCD (thresholds)
- **Method**: Settlement time matching

### Weather Arbitrage Scanner
- **Frequency**: Every 30 seconds
- **Cities**: 7 (NYC, LAX, CHI, MIA, DEN, AUS, PHL)
- **Markets**: 2 types per city (HIGH + LOW temperature)
- **Total**: 14 market series
- **Forecasts**: NWS API with location-specific adjustments

## Weather Markets

Each city has **two** series:
- `KXHIGHNY` - New York daily high temperature
- `KXLOWNY` - New York daily low temperature

All 7 cities × 2 types = **14 total weather series**.

### Location Configs

Each location has:
- **Coordinates** for NWS API
- **Urban heat adjustment** (e.g., NYC +1.5°F for highs)
- **Coastal damping** (e.g., LAX 0.85 damping factor)
- **Base uncertainty** (weather volatility)

Example (NYC):
```python
LocationConfig(
    code="NYC",
    city="New York",
    high_series="KXHIGHNY",
    low_series="KXLOWNY",
    latitude=40.7128,
    longitude=-74.0060,
    urban_heat_adjustment=1.5,  # Urban heat island
    coastal_damping=0.95        # Atlantic influence
)
```

---

## API Endpoints

### Weather Arbitrage
- `GET /weather-arb/status` - Full weather scanner status
- `GET /weather-arb/city/{code}` - Single city (e.g., NYC)
- `GET /weather-arb/history` - Historical scans

### BTC Arbitrage
- `GET /btc-arb/status` - BTC scanner status
- `GET /btc-arb/history` - Historical scans

### Unified
- `GET /scanners/status` - All scanners at once

### Logs
- `GET /logs/recent?lines=100&source=weather&level=INFO`
- `GET /logs/files` - List all log files

---

## Files Created

### Configuration
```
backend/config/
  __init__.py
  fees.py                      # Kalshi fee calculator
  locations/
    __init__.py
    base.py                    # LocationConfig dataclass
    registry.py                # 7 cities × 2 types
```

### Services
```
backend/services/
  log_config.py                # Centralized logging
  scanner_db.py                # SQLite for scanner results
  nws_client.py                # NWS weather API client
  weather_arb_scanner.py       # Weather scanner (14 series)
  scanner_service.py           # Unified scanner runner
  log_viewer.py                # Colored log viewer
```

### Launchers
```
run_scanners.py                # Python -m scanner_service
run_logs.py                    # Python -m log_viewer
start.bat                      # Launch all 4 terminals
stop.bat                       # Kill all terminals
```

---

## Logging

All services log to:
1. **Console** (their terminal window) - colored
2. **Shared log files** (for Terminal 4)

### Log Files
```
logs/
  kalshi.log      # All logs combined
  api.log         # API-specific
  scanners.log    # Scanner-specific
  errors.log      # Errors only
  trades.log      # Trade execution
```

### Log Viewer Filters
```bash
# Watch weather scanner only
python run_logs.py --source weather

# Watch errors only
python run_logs.py --level ERROR

# Search for text
python run_logs.py --text "arbitrage"

# Different log file
python run_logs.py --file errors
```

---

## Database Schema

### scanner_results
```sql
scanner_type TEXT PRIMARY KEY  -- "btc" or "weather"
result_json TEXT               -- Full scanner status as JSON
updated_at TEXT                -- Last update timestamp
```

### scanner_stats
```sql
id INTEGER PRIMARY KEY
scanner_type TEXT
scan_count INTEGER
opportunities_found INTEGER
near_misses_found INTEGER
best_cost INTEGER
timestamp TEXT
```

---

## Performance

### Before (2-terminal)
- Scans blocked API requests
- Frontend experienced delays during scans

### After (4-terminal)
- Scanners write to SQLite independently
- API reads from SQLite instantly (< 1ms)
- Frontend always responsive
- Logs centralized for debugging

---

## Development Workflow

1. **Start all services**: `start.bat`
2. **Watch logs**: Already open in Terminal 4
3. **Test API**: http://localhost:8001/docs
4. **Use frontend**: http://localhost:5173
5. **Stop all**: `stop.bat` or Ctrl+C in launcher

---

## Next Steps

- Frontend: Add Weather tab showing all 14 series
- Frontend: Display NWS forecasts alongside opportunities
- Frontend: City-by-city breakdown with HIGH/LOW split
- Backend: Execute weather arbitrage trades
- Backend: Track weather positions separately

---

## Key Insights

1. **Weather markets are PAIRED** - every city has HIGH and LOW
2. **NWS API is free** - no rate limits for forecasts
3. **Location matters** - urban heat, coastal effects impact forecasts
4. **Uncertainty quantified** - storm forecasts less reliable
5. **Scanner separation** - prevents blocking, enables scaling
