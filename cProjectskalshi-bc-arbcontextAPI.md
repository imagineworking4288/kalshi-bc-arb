

---

## backend/config/

### fees.py
Kalshi fee calculation utilities

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| FeeCalculator.calculate_fee | contracts: int, price: float | int | Kalshi fee: ceil(0.07 * contracts * price * (1-price)) |
| FeeCalculator.calculate_arbitrage_profit | total_cost_cents: int | Tuple[int, int, int] | Calculate gross profit, fees, and net profit |

### locations/base.py
LocationConfig dataclass with weather forecast adjustments

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| LocationConfig | code, city, high_series, low_series, lat, lon, station_id, timezone, etc. | dataclass | Weather location with forecast adjustment parameters |
| LocationConfig.adjust_forecast | raw_temp: float, description: str, is_high: bool | float | Apply urban heat and coastal damping adjustments |
| LocationConfig.get_uncertainty | description: str | float | Calculate forecast uncertainty based on weather conditions |

### locations/registry.py
Weather location definitions for 7 cities

| Function/Constant | Params | Returns | Description |
|----------|--------|---------|-------------|
| LOCATIONS | - | Dict[str, LocationConfig] | All 7 weather locations (NYC, LAX, CHI, MIA, DEN, AUS, PHL) |
| get_location | code: str | Optional[LocationConfig] | Get single location by code |
| get_all_locations | - | List[LocationConfig] | Get all location configs |
| get_all_series | - | List[str] | Get all weather series tickers (14 total: HIGH + LOW) |

---

## backend/services/ (New Services)

### log_config.py
Centralized logging configuration with colored output

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ColoredFormatter | - | LogFormatter | Custom formatter with ANSI color codes for levels |
| setup_logging | service_name: str | Logger | Setup logger with console, file, and rotating handlers |
| LOG_DIR | - | Path | Module constant: logs directory path |
| MAIN_LOG | - | Path | Module constant: main log file path |

### log_viewer.py
Real-time log viewer with filtering and colors

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| Colors | - | class | ANSI color constants for terminal output |
| LogViewer | filename?: str, source?: str, level?: str, text?: str | - | Initialize log viewer with optional filters |
| LogViewer.colorize_line | line: str | str | Add ANSI colors based on log level and source |
| LogViewer.matches_filters | line: str | bool | Check if line matches all active filters |
| LogViewer.tail_file | - | None | Tail log file with real-time updates |
| main | - | None | CLI entry point with argument parsing |

### nws_client.py
National Weather Service API client for weather forecasts

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| NWSClient | - | - | HTTP client for National Weather Service API |
| NWSClient.get_forecast | lat: float, lon: float, location_code?: str | Optional[Dict] | Get weather forecast with high/low temperatures |
| NWSClient._get_gridpoint | lat: float, lon: float | Optional[Tuple] | Get NWS grid coordinates for location |
| NWSClient._parse_forecast | periods: List[Dict], location_code: str | Dict | Parse forecast periods into high/low temperatures |

### scanner_db.py
SQLite database for scanner results (non-blocking architecture)

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ScannerDatabase | db_path?: str | - | Thread-safe SQLite database for scanner results |
| ScannerDatabase.initialize | - | None | Create database file and tables if needed |
| ScannerDatabase.save_scanner_result | scanner_type: str, result: Dict | None | Save scanner result (called by scanner service) |
| ScannerDatabase.get_scanner_result | scanner_type: str | Optional[Dict] | Get latest scanner result (called by API) |
| ScannerDatabase.save_stats | scanner_type: str, stats: Dict | None | Save scanner statistics |
| ScannerDatabase.get_all_stats | - | List[Dict] | Get all scanner statistics |

### scanner_service.py
Unified scanner service running BTC and Weather scanners

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| ScannerService | - | - | Unified service running all scanners independently |
| ScannerService.start | - | None | Start all scanners in parallel |
| ScannerService.stop | - | None | Stop all scanners |
| ScannerService.run_btc_scanner | - | None | BTC scanner loop (every 2 seconds) |
| ScannerService.run_weather_scanner | - | None | Weather scanner loop (every 30 seconds) |
| main | - | None | CLI entry point for scanner service |

### weather_arb_scanner.py
Weather arbitrage scanner for 14 market series (7 cities × 2 types)

| Class/Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| WeatherArbScanner | kalshi_client | - | Scanner for weather market arbitrage opportunities |
| WeatherArbScanner.scan_once | - | Dict | Scan all 14 weather series for bracket arbitrage |
| WeatherArbScanner._analyze_series | location: LocationConfig, series_ticker: str, market_type: str, forecast?: Dict | Dict | Analyze single series (HIGH or LOW) for opportunities |
| WeatherArbScanner._get_series_markets | series_ticker: str | List[Dict] | Get all markets for weather series |
| WeatherArbScanner._calculate_bracket_arbitrage | markets: List[Dict], forecast_temp?: float | Tuple[int, List[Dict]] | Calculate total cost to buy all brackets |
| WeatherArbScanner.get_stats | - | Dict | Get scanner performance statistics |

---

## Root Entry Points

### run_scanners.py
Scanner service entry point

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| main | - | None | Import and run scanner_service.main() |

### run_logs.py
Log viewer entry point

| Function | Params | Returns | Description |
|----------|--------|---------|-------------|
| main | - | None | Import and run log_viewer.main() with CLI args |

