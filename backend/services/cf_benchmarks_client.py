"""CF Benchmarks client for crypto spot prices"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx


@dataclass
class SpotPrice:
    """Represents a spot price for an asset"""
    asset: str
    price: float
    timestamp: datetime
    cached: bool = False


class CFBenchmarksClient:
    """Client for fetching crypto spot prices from CF Benchmarks"""

    # Index IDs for different assets
    INDICES = {
        "BTC": "BRTI",
        "ETH": "ETHUSD_RTI",
    }

    def __init__(
        self,
        base_url: str = "https://www.cfbenchmarks.com/api",
        cache_ttl_seconds: int = 5
    ):
        self.base_url = base_url
        self._cache: Dict[str, tuple[SpotPrice, datetime]] = {}
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)

    async def get_price(self, asset: str) -> Optional[SpotPrice]:
        """
        Fetch current price for an asset.

        Args:
            asset: Asset symbol (BTC or ETH)

        Returns:
            SpotPrice object or None if unavailable
        """
        # Check cache first
        if asset in self._cache:
            cached_price, cached_at = self._cache[asset]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                return SpotPrice(
                    asset=asset,
                    price=cached_price.price,
                    timestamp=cached_price.timestamp,
                    cached=True
                )

        index_id = self.INDICES.get(asset)
        if not index_id:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/summary",
                    params={"id": index_id},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()

                # Parse the response
                payload = data.get("payload", {})
                value = payload.get("value")
                time_str = payload.get("time")

                if value is None or time_str is None:
                    return self._get_cached_fallback(asset)

                # Parse timestamp
                if time_str.endswith("Z"):
                    time_str = time_str[:-1] + "+00:00"
                timestamp = datetime.fromisoformat(time_str)

                price = SpotPrice(
                    asset=asset,
                    price=float(value),
                    timestamp=timestamp,
                    cached=False
                )

                # Update cache
                self._cache[asset] = (price, datetime.utcnow())
                return price

        except Exception:
            # Return cached price if available, even if stale
            return self._get_cached_fallback(asset)

    def _get_cached_fallback(self, asset: str) -> Optional[SpotPrice]:
        """Get cached price as fallback"""
        if asset in self._cache:
            cached_price, _ = self._cache[asset]
            return SpotPrice(
                asset=asset,
                price=cached_price.price,
                timestamp=cached_price.timestamp,
                cached=True
            )
        return None

    async def get_all_prices(self) -> Dict[str, SpotPrice]:
        """
        Fetch prices for all supported assets.

        Returns:
            Dictionary mapping asset symbols to SpotPrice objects
        """
        prices = {}
        for asset in self.INDICES:
            price = await self.get_price(asset)
            if price:
                prices[asset] = price
        return prices

    @classmethod
    def supported_assets(cls) -> list:
        """Get list of supported asset symbols"""
        return list(cls.INDICES.keys())
