"""Registry of all supported weather market locations."""

from typing import Dict, Optional, List
from .base import LocationConfig

# All 7 Kalshi weather cities with BOTH high and low series
LOCATIONS: Dict[str, LocationConfig] = {
    "NYC": LocationConfig(
        code="NYC",
        city="New York",
        high_series="KXHIGHNY",
        low_series="KXLOWTNYC",
        latitude=40.7128,
        longitude=-74.0060,
        station_id="KNYC",  # Central Park
        timezone="America/New_York",
        base_uncertainty=2.5,
        urban_heat_adjustment=1.5,  # Significant urban heat island
        coastal_damping=0.95
    ),

    "LAX": LocationConfig(
        code="LAX",
        city="Los Angeles",
        high_series="KXHIGHLAX",
        low_series="KXLOWTLAX",
        latitude=33.9425,
        longitude=-118.4081,
        station_id="KLAX",
        timezone="America/Los_Angeles",
        base_uncertainty=2.0,  # More predictable climate
        urban_heat_adjustment=1.0,
        coastal_damping=0.85  # Strong marine influence
    ),

    "CHI": LocationConfig(
        code="CHI",
        city="Chicago",
        high_series="KXHIGHCHI",
        low_series="KXLOWTCHI",
        latitude=41.8781,
        longitude=-87.6298,
        station_id="KORD",  # O'Hare
        timezone="America/Chicago",
        base_uncertainty=3.0,  # Lake effect variability
        urban_heat_adjustment=1.2,
        coastal_damping=0.90  # Lake Michigan influence
    ),

    "MIA": LocationConfig(
        code="MIA",
        city="Miami",
        high_series="KXHIGHMIA",
        low_series="KXLOWTMIA",
        latitude=25.7617,
        longitude=-80.1918,
        station_id="KMIA",
        timezone="America/New_York",
        base_uncertainty=2.0,  # Stable tropical climate
        urban_heat_adjustment=0.8,
        coastal_damping=0.80  # Strong ocean influence
    ),

    "DEN": LocationConfig(
        code="DEN",
        city="Denver",
        high_series="KXHIGHDEN",
        low_series="KXLOWTDEN",
        latitude=39.7392,
        longitude=-104.9903,
        station_id="KDEN",
        timezone="America/Denver",
        base_uncertainty=3.5,  # Mountain weather variability
        urban_heat_adjustment=0.5,
        coastal_damping=1.0  # No coastal influence
    ),

    "AUS": LocationConfig(
        code="AUS",
        city="Austin",
        high_series="KXHIGHAUS",
        low_series="KXLOWTAUS",
        latitude=30.2672,
        longitude=-97.7431,
        station_id="KAUS",
        timezone="America/Chicago",
        base_uncertainty=2.5,
        urban_heat_adjustment=1.0,
        coastal_damping=1.0
    ),

    "PHL": LocationConfig(
        code="PHL",
        city="Philadelphia",
        high_series="KXHIGHPHIL",
        low_series="KXLOWTPHIL",
        latitude=39.9526,
        longitude=-75.1652,
        station_id="KPHL",
        timezone="America/New_York",
        base_uncertainty=2.5,
        urban_heat_adjustment=1.3,
        coastal_damping=0.95
    ),
}

def get_location(code: str) -> Optional[LocationConfig]:
    """Get location config by code."""
    return LOCATIONS.get(code.upper())

def get_all_locations() -> List[LocationConfig]:
    """Get all location configs."""
    return list(LOCATIONS.values())

def get_all_series() -> List[str]:
    """Get all series tickers (both high and low)."""
    series = []
    for loc in LOCATIONS.values():
        series.extend(loc.all_series)
    return series
