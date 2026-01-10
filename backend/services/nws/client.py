"""
Production NWS client with Open-Meteo fallback.

Addresses Issues #1-#4:
- #1: Hardcoded grid points (no dynamic lookup)
- #2: Open-Meteo as fallback API
- #3: Adaptive caching based on forecast age
- #4: Circuit breaker pattern
"""

import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from .config import (
    NWS_GRID_POINTS,
    CACHE_CONFIG,
    FALLBACK_CONFIG,
    get_grid_point,
    get_nws_forecast_url,
    get_open_meteo_params,
    normalize_city_code,
    GridPoint,
)

# Use backend logger if available, otherwise standard logging
try:
    from ..log_config import get_logger
    logger = get_logger("nws_client")
except ImportError:
    logger = logging.getLogger("nws_client")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, not making requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for API fault tolerance.

    Issue #4 Fix: Prevents cascading failures when NWS API is down.
    """
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    half_open_successes: int = 0

    def record_success(self) -> None:
        """Record successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= FALLBACK_CONFIG.half_open_requests:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker closed after successful recovery")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.failure_count >= FALLBACK_CONFIG.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def can_request(self) -> bool:
        """Check if requests are allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
                if elapsed >= FALLBACK_CONFIG.recovery_timeout_seconds:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_successes = 0
                    logger.info("Circuit breaker entering half-open state")
                    return True
            return False

        # HALF_OPEN state
        return True


@dataclass
class CacheEntry:
    """Cached forecast with metadata."""
    forecast: "ForecastData"
    fetched_at: datetime
    source: str  # "nws" or "open_meteo"
    forecast_generated_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if cache entry is expired based on adaptive TTL."""
        age_seconds = (datetime.now(timezone.utc) - self.fetched_at).total_seconds()

        # Determine TTL based on forecast age
        if self.forecast_generated_at:
            forecast_age_hours = (datetime.now(timezone.utc) - self.forecast_generated_at).total_seconds() / 3600
        else:
            forecast_age_hours = 0

        if forecast_age_hours < CACHE_CONFIG.fresh_threshold_hours:
            ttl = CACHE_CONFIG.fresh_forecast_ttl
        elif forecast_age_hours > CACHE_CONFIG.stale_threshold_hours:
            ttl = CACHE_CONFIG.stale_forecast_ttl
        else:
            ttl = CACHE_CONFIG.moderate_forecast_ttl

        return age_seconds > ttl


@dataclass
class ForecastData:
    """Unified forecast data structure."""
    city: str
    forecast_high: int
    forecast_low: int
    short_forecast: str = ""
    detailed_forecast: str = ""
    weather_pattern: str = "transitional"
    confidence_level: float = 0.7
    temperature_range_low: Optional[int] = None
    temperature_range_high: Optional[int] = None
    precipitation_probability: Optional[int] = None
    generated_at: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "nws"


class NWSProductionClient:
    """
    Production-ready NWS forecast client.

    Features:
    - Hardcoded grid points (Issue #1)
    - Open-Meteo fallback (Issue #2)
    - Adaptive caching (Issue #3)
    - Circuit breaker (Issue #4)
    """

    NWS_BASE_URL = "https://api.weather.gov"
    USER_AGENT = "KalshiWeatherBot/2.0 (kalshi-bc-arb; production)"

    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._nws_circuit = CircuitBreaker()
        self._open_meteo_circuit = CircuitBreaker()

    async def get_forecast(self, city: str, force_refresh: bool = False) -> Optional[ForecastData]:
        """
        Get weather forecast for a city.

        Args:
            city: City code (e.g., "NYC", "CHI")
            force_refresh: Skip cache and fetch fresh data

        Returns:
            ForecastData or None if both sources fail
        """
        city = normalize_city_code(city)

        # Check cache first (unless force refresh)
        if not force_refresh and city in self._cache:
            entry = self._cache[city]
            if not entry.is_expired():
                logger.debug(f"[{city}] Cache hit (source: {entry.source})")
                return entry.forecast

        # Validate city is supported
        grid_point = get_grid_point(city)
        if not grid_point:
            logger.error(f"[{city}] Unsupported city code")
            return None

        # Try NWS first
        if self._nws_circuit.can_request():
            forecast = await self._fetch_nws(city, grid_point)
            if forecast:
                self._cache_forecast(city, forecast, "nws")
                return forecast

        # Fallback to Open-Meteo
        if self._open_meteo_circuit.can_request():
            forecast = await self._fetch_open_meteo(city, grid_point)
            if forecast:
                self._cache_forecast(city, forecast, "open_meteo")
                return forecast

        # Both sources failed - return stale cache if available
        if city in self._cache:
            logger.warning(f"[{city}] Returning stale cached data")
            return self._cache[city].forecast

        logger.error(f"[{city}] All forecast sources failed")
        return None

    async def _fetch_nws(self, city: str, grid_point: GridPoint) -> Optional[ForecastData]:
        """Fetch forecast from NWS API using hardcoded grid points."""
        # Build URL directly from hardcoded grid point (Issue #1 fix)
        url = f"{self.NWS_BASE_URL}/gridpoints/{grid_point.wfo}/{grid_point.grid_x},{grid_point.grid_y}/forecast"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=FALLBACK_CONFIG.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()

                forecast = self._parse_nws_response(city, data)
                if forecast:
                    self._nws_circuit.record_success()
                    logger.info(f"[{city}] NWS forecast: High {forecast.forecast_high}F, Low {forecast.forecast_low}F")
                    return forecast

            except httpx.TimeoutException:
                logger.warning(f"[{city}] NWS timeout")
                self._nws_circuit.record_failure()
            except httpx.HTTPStatusError as e:
                logger.warning(f"[{city}] NWS HTTP error: {e.response.status_code}")
                self._nws_circuit.record_failure()
            except Exception as e:
                logger.error(f"[{city}] NWS error: {e}")
                self._nws_circuit.record_failure()

        return None

    async def _fetch_open_meteo(self, city: str, grid_point: GridPoint) -> Optional[ForecastData]:
        """
        Fetch forecast from Open-Meteo API (Issue #2 fallback).

        Open-Meteo is free, requires no auth, and has good uptime.
        """
        params = get_open_meteo_params(city)
        if not params:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    FALLBACK_CONFIG.base_url,
                    params=params,
                    timeout=FALLBACK_CONFIG.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()

                forecast = self._parse_open_meteo_response(city, data)
                if forecast:
                    self._open_meteo_circuit.record_success()
                    logger.info(f"[{city}] Open-Meteo forecast: High {forecast.forecast_high}F, Low {forecast.forecast_low}F")
                    return forecast

            except httpx.TimeoutException:
                logger.warning(f"[{city}] Open-Meteo timeout")
                self._open_meteo_circuit.record_failure()
            except httpx.HTTPStatusError as e:
                logger.warning(f"[{city}] Open-Meteo HTTP error: {e.response.status_code}")
                self._open_meteo_circuit.record_failure()
            except Exception as e:
                logger.error(f"[{city}] Open-Meteo error: {e}")
                self._open_meteo_circuit.record_failure()

        return None

    def _parse_nws_response(self, city: str, data: Dict[str, Any]) -> Optional[ForecastData]:
        """Parse NWS API response into ForecastData."""
        try:
            periods = data.get("properties", {}).get("periods", [])
            if not periods:
                return None

            high_temp = None
            low_temp = None
            short_forecast = ""
            detailed_forecast = ""
            generated_at = None

            # Parse generation time
            update_time = data.get("properties", {}).get("updateTime")
            if update_time:
                generated_at = datetime.fromisoformat(update_time.replace("Z", "+00:00"))

            # Extract high and low from forecast periods
            for period in periods:
                is_daytime = period.get("isDaytime", True)
                temp = period.get("temperature")

                if is_daytime and high_temp is None:
                    high_temp = temp
                    short_forecast = period.get("shortForecast", "")
                    detailed_forecast = period.get("detailedForecast", "")
                elif not is_daytime and low_temp is None:
                    low_temp = temp

                if high_temp is not None and low_temp is not None:
                    break

            if high_temp is None:
                return None

            # Determine weather pattern from forecast text
            weather_pattern = self._determine_weather_pattern(short_forecast, detailed_forecast)

            return ForecastData(
                city=city,
                forecast_high=high_temp,
                forecast_low=low_temp or (high_temp - 15),  # Estimate if missing
                short_forecast=short_forecast,
                detailed_forecast=detailed_forecast,
                weather_pattern=weather_pattern,
                confidence_level=0.75,  # NWS generally reliable
                generated_at=generated_at,
                source="nws",
            )

        except Exception as e:
            logger.error(f"[{city}] Failed to parse NWS response: {e}")
            return None

    def _parse_open_meteo_response(self, city: str, data: Dict[str, Any]) -> Optional[ForecastData]:
        """Parse Open-Meteo API response into ForecastData."""
        try:
            daily = data.get("daily", {})
            temps_max = daily.get("temperature_2m_max", [])
            temps_min = daily.get("temperature_2m_min", [])
            precip_prob = daily.get("precipitation_probability_max", [])

            if not temps_max:
                return None

            # Get today's forecast (index 0)
            high_temp = int(round(temps_max[0]))
            low_temp = int(round(temps_min[0])) if temps_min else high_temp - 15
            precip = precip_prob[0] if precip_prob else None

            # Estimate weather pattern from precipitation probability
            if precip is not None:
                if precip > 60:
                    weather_pattern = "stormy"
                elif precip > 30:
                    weather_pattern = "transitional"
                else:
                    weather_pattern = "stable"
            else:
                weather_pattern = "transitional"

            return ForecastData(
                city=city,
                forecast_high=high_temp,
                forecast_low=low_temp,
                short_forecast=f"Precipitation chance: {precip}%" if precip else "",
                weather_pattern=weather_pattern,
                confidence_level=0.65,  # Slightly lower than NWS
                precipitation_probability=precip,
                generated_at=datetime.now(timezone.utc),
                source="open_meteo",
            )

        except Exception as e:
            logger.error(f"[{city}] Failed to parse Open-Meteo response: {e}")
            return None

    def _determine_weather_pattern(self, short_forecast: str, detailed_forecast: str) -> str:
        """
        Determine weather pattern from forecast text.

        Returns one of: stable, transitional, stormy, frontal
        """
        text = (short_forecast + " " + detailed_forecast).lower()

        # Check for storm indicators
        storm_keywords = ["thunderstorm", "severe", "tornado", "hurricane", "tropical"]
        if any(kw in text for kw in storm_keywords):
            return "stormy"

        # Check for frontal indicators
        frontal_keywords = ["front", "cold front", "warm front", "pressure system"]
        if any(kw in text for kw in frontal_keywords):
            return "frontal"

        # Check for unstable weather
        unstable_keywords = ["rain", "shower", "snow", "windy", "gusts", "changing"]
        if any(kw in text for kw in unstable_keywords):
            return "transitional"

        # Check for stable weather
        stable_keywords = ["clear", "sunny", "fair", "calm", "high pressure"]
        if any(kw in text for kw in stable_keywords):
            return "stable"

        # Default to transitional
        return "transitional"

    def _cache_forecast(self, city: str, forecast: ForecastData, source: str) -> None:
        """Cache forecast with adaptive TTL."""
        # Evict oldest entries if cache is full
        if len(self._cache) >= CACHE_CONFIG.max_entries:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].fetched_at)
            del self._cache[oldest_key]

        self._cache[city] = CacheEntry(
            forecast=forecast,
            fetched_at=datetime.now(timezone.utc),
            source=source,
            forecast_generated_at=forecast.generated_at,
        )

    def get_cache_info(self, city: str) -> Optional[Dict[str, Any]]:
        """Get cache information for a city."""
        city = normalize_city_code(city)
        if city not in self._cache:
            return None

        entry = self._cache[city]
        age_seconds = (datetime.now(timezone.utc) - entry.fetched_at).total_seconds()

        return {
            "city": city,
            "source": entry.source,
            "fetched_at": entry.fetched_at.isoformat(),
            "age_seconds": age_seconds,
            "is_expired": entry.is_expired(),
        }

    def get_circuit_status(self) -> Dict[str, str]:
        """Get circuit breaker status for both APIs."""
        return {
            "nws": self._nws_circuit.state.value,
            "open_meteo": self._open_meteo_circuit.state.value,
        }

    def clear_cache(self) -> None:
        """Clear all cached forecasts."""
        self._cache.clear()

    def reset_circuits(self) -> None:
        """Reset both circuit breakers to closed state."""
        self._nws_circuit = CircuitBreaker()
        self._open_meteo_circuit = CircuitBreaker()


# Singleton instance
_client: Optional[NWSProductionClient] = None


def get_client() -> NWSProductionClient:
    """Get singleton client instance."""
    global _client
    if _client is None:
        _client = NWSProductionClient()
    return _client


async def get_forecast(city: str, force_refresh: bool = False) -> Optional[ForecastData]:
    """Convenience function to get forecast using singleton client."""
    return await get_client().get_forecast(city, force_refresh)
