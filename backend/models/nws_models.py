"""
Models for National Weather Service forecast data.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum


class WeatherPattern(str, Enum):
    """Weather pattern affects forecast uncertainty"""
    STABLE = "stable"           # High pressure, clear - low uncertainty
    TRANSITIONAL = "transitional"  # Changing conditions - medium uncertainty
    STORMY = "stormy"           # Active weather - high uncertainty
    FRONTAL = "frontal"         # Front passage - very high uncertainty


class ForecastPeriod(BaseModel):
    """Single forecast period from NWS"""
    number: int
    name: str  # e.g., "Today", "Tonight", "Saturday"
    start_time: datetime
    end_time: datetime

    is_daytime: bool
    temperature: int  # Fahrenheit
    temperature_unit: str = "F"
    temperature_trend: Optional[str] = None

    # Probability of precipitation
    probability_of_precipitation: Optional[int] = Field(default=None, ge=0, le=100)

    # Wind
    wind_speed: Optional[str] = None
    wind_direction: Optional[str] = None

    # Conditions
    short_forecast: str
    detailed_forecast: str
    icon: Optional[str] = None

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v


class HourlyForecast(BaseModel):
    """Hourly forecast point"""
    valid_time: datetime
    temperature: int
    temperature_unit: str = "F"
    probability_of_precipitation: Optional[int] = None
    wind_speed_mph: Optional[int] = None
    sky_cover: Optional[int] = None  # Cloud cover percentage

    @field_validator('valid_time', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            # NWS format: "2025-01-10T14:00:00-05:00/PT1H"
            if '/' in v:
                v = v.split('/')[0]
            return datetime.fromisoformat(v)
        return v


class NWSForecast(BaseModel):
    """
    Complete NWS forecast for a location.
    Used by probability engine to estimate bracket probabilities.
    """
    # Location info
    city: str
    station_id: str  # e.g., "KNYC" for Central Park
    grid_id: str  # WFO code
    grid_x: int
    grid_y: int

    # Forecast data
    forecast_high: int  # Predicted high temperature
    forecast_low: int

    # Uncertainty estimation
    temperature_range_low: Optional[int] = None  # Low end of range
    temperature_range_high: Optional[int] = None  # High end of range

    # Derived uncertainty
    weather_pattern: WeatherPattern = WeatherPattern.TRANSITIONAL
    confidence_level: float = Field(default=0.7, ge=0.0, le=1.0)

    # Hourly data for more precise estimates
    hourly_forecasts: List[HourlyForecast] = Field(default_factory=list)

    # Metadata
    generated_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def forecast_std_dev(self) -> float:
        """
        Estimate standard deviation based on conditions.

        Research shows:
        - Stable conditions: ~1.5°F std dev
        - Transitional: ~3.0°F std dev
        - Stormy/Frontal: ~4.5°F std dev

        Also adjust for confidence level and range if provided.
        """
        # Base std dev by pattern
        base_std = {
            WeatherPattern.STABLE: 1.5,
            WeatherPattern.TRANSITIONAL: 3.0,
            WeatherPattern.STORMY: 4.5,
            WeatherPattern.FRONTAL: 5.0,
        }.get(self.weather_pattern, 3.0)

        # If NWS provides a range, use it
        if self.temperature_range_low and self.temperature_range_high:
            range_width = self.temperature_range_high - self.temperature_range_low
            # Assume range is ~2 standard deviations (95%)
            range_std = range_width / 4.0
            # Blend with pattern-based estimate
            base_std = (base_std + range_std) / 2.0

        # Adjust for confidence
        # Lower confidence = higher uncertainty
        confidence_multiplier = 1.0 + (1.0 - self.confidence_level) * 0.5

        return base_std * confidence_multiplier

    def expected_high_at_hour(self, hour: int) -> Optional[int]:
        """Get expected temperature at specific hour"""
        for hf in self.hourly_forecasts:
            if hf.valid_time.hour == hour:
                return hf.temperature
        return None

    def max_hourly_temp(self) -> Optional[int]:
        """Maximum temperature from hourly forecasts"""
        if not self.hourly_forecasts:
            return None
        return max(hf.temperature for hf in self.hourly_forecasts)

    def is_stale(self, max_age_hours: float = 1.0) -> bool:
        """Check if forecast is too old"""
        age = (datetime.now(timezone.utc) - self.fetched_at).total_seconds()
        return age > max_age_hours * 3600


class ClimatologyData(BaseModel):
    """
    Historical climate data for bias correction.
    Used to adjust forecasts based on historical accuracy.
    """
    city: str
    month: int
    day: int

    # Historical averages
    avg_high: float
    avg_low: float
    record_high: int
    record_low: int

    # Forecast bias (forecast - actual, historically)
    high_temp_bias: float = 0.0  # Positive = forecasts run warm
    std_dev_historical: float = 3.0

    # Sample size
    years_of_data: int = 30


class LocationConfig(BaseModel):
    """
    Configuration for a weather market location.
    Maps Kalshi series to NWS data sources.
    """
    city: str
    series_ticker: str  # e.g., "KXHIGHNY"

    # NWS identifiers
    station_id: str  # e.g., "KNYC"
    wfo: str  # Weather Forecast Office
    grid_x: int
    grid_y: int

    # Coordinates
    latitude: float
    longitude: float

    # Timezone
    timezone: str  # e.g., "America/New_York"

    # Market characteristics
    typical_std_dev: float = 3.0
    settlement_hour: int = 23  # When CLI is generated

    # Historical bias correction
    forecast_bias: float = 0.0


# Pre-configured locations for Kalshi weather markets
KALSHI_LOCATIONS = {
    "NYC": LocationConfig(
        city="New York",
        series_ticker="KXHIGHNY",
        station_id="KNYC",
        wfo="OKX",
        grid_x=33,
        grid_y=37,
        latitude=40.7128,
        longitude=-74.0060,
        timezone="America/New_York",
        typical_std_dev=2.8,
    ),
    "CHI": LocationConfig(
        city="Chicago",
        series_ticker="KXHIGHCHI",
        station_id="KMDW",
        wfo="LOT",
        grid_x=65,
        grid_y=76,
        latitude=41.8781,
        longitude=-87.6298,
        timezone="America/Chicago",
        typical_std_dev=3.2,
    ),
    "MIA": LocationConfig(
        city="Miami",
        series_ticker="KXHIGHMIA",
        station_id="KMIA",
        wfo="MFL",
        grid_x=109,
        grid_y=50,
        latitude=25.7617,
        longitude=-80.1918,
        timezone="America/New_York",
        typical_std_dev=2.2,
    ),
    "AUS": LocationConfig(
        city="Austin",
        series_ticker="KXHIGHAUS",
        station_id="KAUS",
        wfo="EWX",
        grid_x=157,
        grid_y=97,
        latitude=30.2672,
        longitude=-97.7431,
        timezone="America/Chicago",
        typical_std_dev=3.5,
    ),
    "LAX": LocationConfig(
        city="Los Angeles",
        series_ticker="KXHIGHLAX",
        station_id="KLAX",
        wfo="LOX",
        grid_x=154,
        grid_y=44,
        latitude=34.0522,
        longitude=-118.2437,
        timezone="America/Los_Angeles",
        typical_std_dev=3.0,
    ),
    "DEN": LocationConfig(
        city="Denver",
        series_ticker="KXHIGHDEN",
        station_id="KDEN",
        wfo="BOU",
        grid_x=62,
        grid_y=60,
        latitude=39.7392,
        longitude=-104.9903,
        timezone="America/Denver",
        typical_std_dev=4.0,
    ),
}
