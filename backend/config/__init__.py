"""
Configuration module for Kalshi trading platform.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Kalshi API
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: str = "./kalshi_private_key.pem"

    # API URLs
    kalshi_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    kalshi_ws_url: str = "wss://api.elections.kalshi.com/trade-api/ws/v2"

    # Trading settings
    paper_trading: bool = True
    paper_trading_mode: bool = True  # Alias for compatibility
    initial_paper_balance: int = 10000  # cents
    paper_starting_balance: float = 10000.00  # dollars (for compatibility)

    # Scanner settings
    btc_scan_interval: float = 2.0
    weather_scan_interval: float = 30.0
    auto_start_scanning: bool = False  # Auto-start orchestrator on startup

    # Database
    database_path: str = "./data/kalshi.db"
    scanner_db_path: str = "./data/scanner_results.db"

    # Logging
    log_level: str = "INFO"

    @property
    def has_kalshi_credentials(self) -> bool:
        """Check if API key and private key path exist"""
        return bool(self.kalshi_api_key_id) and Path(self.kalshi_private_key_path).exists()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


# Export location configs if available
try:
    from .locations import LocationConfig, LOCATIONS, get_location, get_all_locations, get_all_series
except ImportError:
    # Locations module not yet created
    pass
