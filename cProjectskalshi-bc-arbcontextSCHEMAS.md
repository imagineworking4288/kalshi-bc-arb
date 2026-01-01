
---

## Weather Configuration Schemas

### LocationConfig (backend/config/locations/base.py)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| code | str | - | Location code (e.g., "NYC", "LAX") |
| city | str | - | Full city name |
| high_series | str | - | High temperature series ticker (e.g., "KXHIGHNY") |
| low_series | str | - | Low temperature series ticker (e.g., "KXLOWNY") |
| latitude | float | - | Location latitude for NWS API |
| longitude | float | - | Location longitude for NWS API |
| station_id | str | - | Weather station identifier |
| timezone | str | - | IANA timezone (e.g., "America/New_York") |
| base_uncertainty | float | 2.5 | Base forecast uncertainty in degrees |
| max_uncertainty | float | 5.0 | Maximum uncertainty for storms |
| urban_heat_adjustment | float | 0.0 | Urban heat island effect (degrees) |
| coastal_damping | float | 1.0 | Coastal moderation factor (0.0-1.0) |

---

## Scanner Database Tables

### scanner_results (data/scanner_results.db)

| Field | Type | Description |
|-------|------|-------------|
| scanner_type | TEXT PRIMARY KEY | Scanner type: "btc" or "weather" |
| result_json | TEXT | Full scanner status as JSON |
| updated_at | TEXT | Last update timestamp (ISO format) |

### scanner_stats (data/scanner_results.db)

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| scanner_type | TEXT | Scanner type: "btc" or "weather" |
| scan_count | INTEGER | Total number of scans performed |
| opportunities_found | INTEGER | Total opportunities detected |
| near_misses_found | INTEGER | Total near-misses found |
| best_cost | INTEGER | Best cost found (cents) |
| timestamp | TEXT | Scan timestamp (ISO format) |

---

## Weather Arbitrage Schemas

### WeatherScanResult (backend/services/weather_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| scan_count | int | Total scans performed |
| timestamp | str | ISO timestamp of scan |
| cities | Dict[str, CityResult] | Results by city code |
| opportunities | List[Dict] | Found arbitrage opportunities |
| count | int | Number of opportunities |
| total_scanned | int | Total markets scanned |
| total_brackets | Dict[str, int] | Brackets by type (high/low) |
| near_misses | int | Near-miss opportunities |
| scan_duration_ms | int | Scan duration in milliseconds |

### CityResult (backend/services/weather_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| city | str | City name |
| code | str | Location code |
| high | SeriesResult | High temperature results |
| low | SeriesResult | Low temperature results |
| forecast | Dict \| None | NWS forecast data |

### SeriesResult (backend/services/weather_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| series_ticker | str | Market series ticker |
| markets_count | int | Number of markets found |
| total_cost | int \| None | Total cost to buy all brackets (cents) |
| opportunity | Dict \| None | Arbitrage opportunity if profitable |
| near_miss | Dict \| None | Near-miss data if close |
| forecast_temp | float \| None | Forecast temperature |
| error | str \| None | Error message if scan failed |

---

## BTC Arbitrage Enhanced Schemas

### BTCScanResult (backend/services/btc_arb_scanner.py)

| Field | Type | Description |
|-------|------|-------------|
| opportunities | List[Dict] | Found arbitrage opportunities |
| count | int | Number of opportunities |
| scan_count | int | Total scans performed |
| last_scan_duration_ms | int | Duration of last scan |
| timestamp | str | ISO timestamp |
| stats | Dict | Scan statistics and metrics |

### ScannerServiceStatus (backend/services/scanner_service.py)

| Field | Type | Description |
|-------|------|-------------|
| btc | Dict | BTC scanner status and results |
| weather | Dict | Weather scanner status and results |
| running | bool | Whether service is running |
| startup_time | str | Service startup timestamp |

