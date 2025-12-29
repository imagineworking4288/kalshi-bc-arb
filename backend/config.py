from pydantic_settings import BaseSettings
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Kalshi Configuration
    kalshi_env: Literal["demo", "production"] = "demo"
    kalshi_demo_api_url: str = "https://demo-api.kalshi.co/trade-api/v2"
    kalshi_prod_api_url: str = "https://trading-api.kalshi.com/trade-api/v2"
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: str = "./keys/kalshi-private-key.pem"

    # CF Benchmarks Configuration
    cf_benchmarks_api_url: str = "https://www.cfbenchmarks.com/api"

    # Application Settings
    log_level: str = "INFO"
    database_path: str = "./data/kalshi_arb.db"

    @property
    def kalshi_api_url(self) -> str:
        """Get the correct API URL based on environment"""
        if self.kalshi_env == "production":
            return self.kalshi_prod_api_url
        return self.kalshi_demo_api_url

    @property
    def kalshi_ws_url(self) -> str:
        """Convert REST URL to WebSocket URL"""
        base = self.kalshi_api_url.replace("https://", "wss://")
        return base.replace("/trade-api/v2", "/trade-api/ws/v2")

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.kalshi_env == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
