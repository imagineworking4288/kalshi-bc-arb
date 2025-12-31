"""
Application settings from environment variables
Updated for new Kalshi API endpoint: api.elections.kalshi.com
"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Kalshi API - NEW URL
    kalshi_api_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: str = "./keys/kalshi-private-key.pem"

    # Paper trading simulation
    paper_trading_mode: bool = True  # DEFAULT TO SAFE MODE
    paper_starting_balance: float = 10000.00

    # Application settings
    database_path: str = "./data/kalshi_arb.db"
    log_level: str = "INFO"

    @property
    def kalshi_ws_url(self) -> str:
        """Derive WebSocket URL from API URL"""
        return self.kalshi_api_url.replace("https://", "wss://").replace("/trade-api/v2", "/trade-api/ws/v2")

    @property
    def has_kalshi_credentials(self) -> bool:
        """Check if API key and private key path exist"""
        return bool(self.kalshi_api_key_id) and Path(self.kalshi_private_key_path).exists()

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton"""
    return Settings()
