"""
Spot price client for BTC using free APIs (CoinGecko primary, CoinLore fallback)

Replaces the CF Benchmarks client which now requires paid authentication.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import httpx
import logging

logger = logging.getLogger(__name__)


@dataclass
class SpotPrice:
    asset: str
    price: float
    timestamp: datetime
    source: str = "unknown"


class SpotPriceClient:
    """Fetch spot prices from free crypto APIs with fallback support."""

    def __init__(self, base_url: str = None):  # base_url kept for backward compatibility
        self._cache: dict[str, SpotPrice] = {}
        self._cache_ttl_seconds = 10

        # Free API endpoints (no auth required)
        self.coingecko_url = "https://api.coingecko.com/api/v3/simple/price"
        self.coinlore_url = "https://api.coinlore.net/api/ticker/"

        # Coin ID mappings
        self.coinlore_ids = {"BTC": "90", "ETH": "80"}
        self.coingecko_ids = {"BTC": "bitcoin", "ETH": "ethereum"}

    async def get_price(self, asset: str = "BTC") -> Optional[SpotPrice]:
        """Fetch current spot price with caching and fallback."""
        # Check cache
        cached = self._cache.get(asset)
        if cached:
            age = (datetime.utcnow() - cached.timestamp).total_seconds()
            if age < self._cache_ttl_seconds:
                return cached

        # Try CoinGecko first (better data, but rate limited)
        price = await self._fetch_coingecko(asset)
        if price:
            self._cache[asset] = price
            return price

        # Fallback to CoinLore
        price = await self._fetch_coinlore(asset)
        if price:
            self._cache[asset] = price
            return price

        logger.error(f"All price sources failed for {asset}")
        return None

    async def _fetch_coingecko(self, asset: str) -> Optional[SpotPrice]:
        """Fetch from CoinGecko (free: 30 calls/min)."""
        coin_id = self.coingecko_ids.get(asset)
        if not coin_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.coingecko_url,
                    params={"ids": coin_id, "vs_currencies": "usd", "precision": "2"}
                )
                response.raise_for_status()
                data = response.json()

                price_usd = data.get(coin_id, {}).get("usd")
                if price_usd is None:
                    return None

                return SpotPrice(
                    asset=asset,
                    price=float(price_usd),
                    timestamp=datetime.utcnow(),
                    source="CoinGecko"
                )
        except Exception as e:
            logger.warning(f"CoinGecko error: {e}")
            return None

    async def _fetch_coinlore(self, asset: str) -> Optional[SpotPrice]:
        """Fetch from CoinLore (free, no published rate limit)."""
        coin_id = self.coinlore_ids.get(asset)
        if not coin_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.coinlore_url,
                    params={"id": coin_id}
                )
                response.raise_for_status()
                data = response.json()

                if not data:
                    return None

                price_usd = data[0].get("price_usd")
                if price_usd is None:
                    return None

                return SpotPrice(
                    asset=asset,
                    price=float(price_usd),
                    timestamp=datetime.utcnow(),
                    source="CoinLore"
                )
        except Exception as e:
            logger.warning(f"CoinLore error: {e}")
            return None
