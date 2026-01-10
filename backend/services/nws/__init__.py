"""
NWS (National Weather Service) client package.

Provides production-ready forecast fetching with:
- Hardcoded grid points (no dynamic lookup)
- Open-Meteo API fallback
- Adaptive caching
- Circuit breaker pattern
"""

from .config import (
    NWS_GRID_POINTS,
    CACHE_CONFIG,
    FALLBACK_CONFIG,
    get_grid_point,
)

from .client import (
    NWSProductionClient,
    get_forecast,
)

__all__ = [
    'NWS_GRID_POINTS',
    'CACHE_CONFIG',
    'FALLBACK_CONFIG',
    'get_grid_point',
    'NWSProductionClient',
    'get_forecast',
]
