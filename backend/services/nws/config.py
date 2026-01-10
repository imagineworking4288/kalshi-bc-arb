"""
NWS configuration with hardcoded grid points.

Issue #1 Fix: No dynamic grid point lookup - all coordinates are hardcoded.
This eliminates the /points API call that frequently fails.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class GridPoint:
    """NWS grid point coordinates."""
    wfo: str          # Weather Forecast Office code (e.g., "OKX")
    grid_x: int       # Grid X coordinate
    grid_y: int       # Grid Y coordinate
    latitude: float   # For Open-Meteo fallback
    longitude: float  # For Open-Meteo fallback
    timezone: str     # IANA timezone


# Hardcoded NWS grid points for all Kalshi weather markets
# Issue #1 Fix: These are manually verified coordinates
NWS_GRID_POINTS: Dict[str, GridPoint] = {
    # New York City - Central Park
    "NYC": GridPoint(
        wfo="OKX",
        grid_x=33,
        grid_y=37,
        latitude=40.7128,
        longitude=-74.0060,
        timezone="America/New_York",
    ),
    # Chicago - Midway Airport
    "CHI": GridPoint(
        wfo="LOT",
        grid_x=65,
        grid_y=76,
        latitude=41.8781,
        longitude=-87.6298,
        timezone="America/Chicago",
    ),
    # Miami International Airport
    "MIA": GridPoint(
        wfo="MFL",
        grid_x=109,
        grid_y=50,
        latitude=25.7617,
        longitude=-80.1918,
        timezone="America/New_York",
    ),
    # Austin - Camp Mabry
    "AUS": GridPoint(
        wfo="EWX",
        grid_x=157,
        grid_y=97,
        latitude=30.2672,
        longitude=-97.7431,
        timezone="America/Chicago",
    ),
    # Los Angeles International Airport
    "LAX": GridPoint(
        wfo="LOX",
        grid_x=154,
        grid_y=44,
        latitude=34.0522,
        longitude=-118.2437,
        timezone="America/Los_Angeles",
    ),
    # Denver International Airport
    "DEN": GridPoint(
        wfo="BOU",
        grid_x=62,
        grid_y=60,
        latitude=39.7392,
        longitude=-104.9903,
        timezone="America/Denver",
    ),
    # Philadelphia - Philadelphia International Airport
    "PHL": GridPoint(
        wfo="PHI",
        grid_x=49,
        grid_y=76,
        latitude=39.8744,
        longitude=-75.2424,
        timezone="America/New_York",
    ),
}


@dataclass(frozen=True)
class CacheConfig:
    """Cache configuration with adaptive TTL."""
    # Base TTL in seconds
    default_ttl: int = 300  # 5 minutes

    # TTL adjustments based on forecast age
    fresh_forecast_ttl: int = 600    # 10 min for forecasts < 1 hour old
    moderate_forecast_ttl: int = 300  # 5 min for forecasts 1-6 hours old
    stale_forecast_ttl: int = 120     # 2 min for forecasts > 6 hours old

    # Time boundaries (hours) for TTL selection
    fresh_threshold_hours: float = 1.0
    stale_threshold_hours: float = 6.0

    # Maximum cache size
    max_entries: int = 100


# Issue #3 Fix: Adaptive caching configuration
CACHE_CONFIG = CacheConfig()


@dataclass(frozen=True)
class FallbackConfig:
    """Open-Meteo fallback configuration."""
    # Open-Meteo API (free, no auth needed)
    base_url: str = "https://api.open-meteo.com/v1/forecast"

    # Request timeout
    timeout_seconds: float = 10.0

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Circuit breaker settings (Issue #4 Fix)
    failure_threshold: int = 3       # Failures before opening circuit
    recovery_timeout_seconds: int = 60  # Time before trying again
    half_open_requests: int = 1      # Requests to try in half-open state


# Issue #2 Fix: Open-Meteo fallback configuration
FALLBACK_CONFIG = FallbackConfig()


def get_grid_point(city: str) -> Optional[GridPoint]:
    """
    Get grid point for a city.

    Args:
        city: City code (e.g., "NYC", "CHI")

    Returns:
        GridPoint if city is supported, None otherwise
    """
    return NWS_GRID_POINTS.get(city.upper())


def get_nws_forecast_url(city: str) -> Optional[str]:
    """
    Build NWS forecast URL from hardcoded grid point.

    Args:
        city: City code

    Returns:
        Full forecast URL or None if city not supported
    """
    grid_point = get_grid_point(city)
    if not grid_point:
        return None

    return f"https://api.weather.gov/gridpoints/{grid_point.wfo}/{grid_point.grid_x},{grid_point.grid_y}/forecast"


def get_open_meteo_params(city: str) -> Optional[Dict]:
    """
    Build Open-Meteo API parameters for a city.

    Args:
        city: City code

    Returns:
        Dict of query parameters or None if city not supported
    """
    grid_point = get_grid_point(city)
    if not grid_point:
        return None

    return {
        "latitude": grid_point.latitude,
        "longitude": grid_point.longitude,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_probability_max"],
        "temperature_unit": "fahrenheit",
        "timezone": grid_point.timezone,
        "forecast_days": 3,
    }


# City code aliases for flexibility
CITY_ALIASES: Dict[str, str] = {
    "NEW YORK": "NYC",
    "NEW_YORK": "NYC",
    "NY": "NYC",
    "CHICAGO": "CHI",
    "MIAMI": "MIA",
    "AUSTIN": "AUS",
    "LOS ANGELES": "LAX",
    "LOS_ANGELES": "LAX",
    "LA": "LAX",
    "DENVER": "DEN",
    "PHILADELPHIA": "PHL",
    "PHILLY": "PHL",
}


def normalize_city_code(city: str) -> str:
    """Normalize city name to standard code."""
    upper = city.upper().strip()
    return CITY_ALIASES.get(upper, upper)
