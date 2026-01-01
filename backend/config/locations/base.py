"""Base location configuration for weather markets."""

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class LocationConfig:
    """Configuration for a weather market location."""

    # Identifiers
    code: str                    # "NYC", "LAX", etc.
    city: str                    # "New York", "Los Angeles"

    # Kalshi series tickers - BOTH high and low
    high_series: str             # "KXHIGHNY"
    low_series: str              # "KXLOWNY"

    # NWS API coordinates
    latitude: float
    longitude: float
    station_id: str              # NWS station for settlement

    # Timezone
    timezone: str                # "America/New_York"

    # Forecast adjustments
    base_uncertainty: float = 2.5      # Base temp uncertainty in °F
    max_uncertainty: float = 5.0       # Max uncertainty for poor forecasts
    urban_heat_adjustment: float = 0.0 # Urban heat island effect
    coastal_damping: float = 1.0       # Coastal temperature damping (1.0 = none)

    @property
    def all_series(self) -> List[str]:
        """Get both series tickers."""
        return [self.high_series, self.low_series]

    def adjust_forecast(self, raw_temp: float, description: str, is_high: bool = True) -> float:
        """
        Adjust raw NWS forecast based on location characteristics.

        Args:
            raw_temp: Raw temperature from NWS
            description: Forecast description (for cloud/wind adjustments)
            is_high: True for high temp, False for low temp
        """
        adjusted = raw_temp

        # Urban heat island - stronger effect on highs
        if is_high:
            adjusted += self.urban_heat_adjustment
        else:
            # Low temps see about half the urban heat effect
            adjusted += self.urban_heat_adjustment * 0.5

        # Coastal damping reduces extremes
        if self.coastal_damping < 1.0:
            # Dampen deviation from 65°F baseline
            baseline = 65.0
            deviation = adjusted - baseline
            adjusted = baseline + (deviation * self.coastal_damping)

        return round(adjusted, 1)

    def calculate_uncertainty(self, description: str, is_high: bool = True) -> float:
        """
        Calculate forecast uncertainty based on conditions.

        Args:
            description: Forecast description
            is_high: True for high temp, False for low temp
        """
        uncertainty = self.base_uncertainty
        desc_lower = description.lower() if description else ""

        # Increase uncertainty for problematic conditions
        if any(word in desc_lower for word in ['thunder', 'storm', 'severe']):
            uncertainty += 2.0
        elif any(word in desc_lower for word in ['shower', 'rain', 'snow']):
            uncertainty += 1.5
        elif any(word in desc_lower for word in ['cloudy', 'overcast']):
            uncertainty += 0.5

        # Wind increases uncertainty
        if any(word in desc_lower for word in ['windy', 'breezy', 'gusty']):
            uncertainty += 0.5

        # Low temps slightly more uncertain (radiative cooling variability)
        if not is_high:
            uncertainty += 0.3

        return min(uncertainty, self.max_uncertainty)
