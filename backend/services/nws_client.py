"""
National Weather Service API Client

Fetches forecasts for weather market trading.
Returns BOTH high and low temperatures.
"""

import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass
import asyncio
from .log_config import get_logger

logger = get_logger("nws_client")

@dataclass
class WeatherForecast:
    """Weather forecast data."""
    high: Optional[int]
    low: Optional[int]
    high_description: str
    low_description: str
    high_detailed: str
    low_detailed: str
    fetched_at: str
    location_code: str
    forecast_date: str
    raw_periods: list

class NWSClient:
    """Client for National Weather Service API."""

    BASE_URL = "https://api.weather.gov"
    USER_AGENT = "KalshiWeatherBot/1.0 (contact@example.com)"

    def __init__(self):
        self._point_cache: Dict[str, Dict] = {}
        self._forecast_cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # 5 minutes

    async def _get_point_metadata(self, lat: float, lon: float) -> Optional[Dict]:
        """Get NWS grid point for coordinates."""
        cache_key = f"{lat},{lon}"

        if cache_key in self._point_cache:
            return self._point_cache[cache_key]

        url = f"{self.BASE_URL}/points/{lat},{lon}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                self._point_cache[cache_key] = data["properties"]
                return data["properties"]
            except Exception as e:
                logger.error(f"Failed to get NWS point metadata: {e}")
                return None

    async def get_forecast(self, lat: float, lon: float, location_code: str = "UNK") -> Optional[Dict]:
        """
        Get weather forecast for coordinates.

        Returns dict with BOTH high and low temperatures:
        {
            "high": 42,
            "low": 28,
            "high_description": "Partly Cloudy",
            "low_description": "Clear",
            "high_detailed": "...",
            "low_detailed": "...",
            "fetched_at": "...",
            "location_code": "NYC",
            "forecast_date": "2026-01-01",
            "raw_periods": [...]
        }
        """
        # Get grid point
        point = await self._get_point_metadata(lat, lon)
        if not point:
            return None

        forecast_url = point.get("forecast")
        if not forecast_url:
            logger.error("No forecast URL in point metadata")
            return None

        # Fetch forecast
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    forecast_url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.error(f"Failed to fetch NWS forecast: {e}")
                return None

        periods = data.get("properties", {}).get("periods", [])
        if not periods:
            logger.error("No forecast periods in response")
            return None

        # Find today's high and low
        today = datetime.now().strftime("%Y-%m-%d")

        high_temp = None
        low_temp = None
        high_desc = ""
        low_desc = ""
        high_detailed = ""
        low_detailed = ""

        for period in periods:
            # NWS periods alternate day/night
            is_daytime = period.get("isDaytime", True)
            temp = period.get("temperature")

            if is_daytime and high_temp is None:
                high_temp = temp
                high_desc = period.get("shortForecast", "")
                high_detailed = period.get("detailedForecast", "")
            elif not is_daytime and low_temp is None:
                low_temp = temp
                low_desc = period.get("shortForecast", "")
                low_detailed = period.get("detailedForecast", "")

            if high_temp is not None and low_temp is not None:
                break

        result = {
            "high": high_temp,
            "low": low_temp,
            "high_description": high_desc,
            "low_description": low_desc,
            "high_detailed": high_detailed,
            "low_detailed": low_detailed,
            "fetched_at": datetime.now().isoformat(),
            "location_code": location_code,
            "forecast_date": today,
            "raw_periods": periods[:4]  # Keep first 4 periods for debugging
        }

        logger.info(f"[{location_code}] Forecast: High {high_temp}°F, Low {low_temp}°F")

        return result
