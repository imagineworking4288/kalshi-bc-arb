from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # Kalshi API (single production endpoint)
    kalshi_api_url: str = "https://trading-api.kalshi.com/trade-api/v2"
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: str = "./keys/kalshi-private-key.pem"

    # Trading mode: True = paper (simulate locally), False = live (real money)
    paper_trading_mode: bool = True
    paper_starting_balance: float = 10000.00

    # Spot prices
    cf_benchmarks_api_url: str = "https://www.cfbenchmarks.com/api"

    # App
    database_path: str = "./data/kalshi_arb.db"
    log_level: str = "INFO"

    @property
    def kalshi_ws_url(self) -> str:
        return self.kalshi_api_url.replace("https://", "wss://").replace("/trade-api/v2", "/trade-api/ws/v2")

    @property
    def has_kalshi_credentials(self) -> bool:
        return bool(self.kalshi_api_key_id) and Path(self.kalshi_private_key_path).exists()

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
