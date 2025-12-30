import httpx
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass


@dataclass
class SpotPrice:
    asset: str
    price: float
    timestamp: datetime


class SpotPriceClient:
    """Fetches BTC spot price from CF Benchmarks"""

    ASSET_INDEX_MAP = {
        "BTC": "BRTI",  # Bitcoin Real-Time Index
    }

    def __init__(self, base_url: str = "https://www.cfbenchmarks.com/api"):
        self.base_url = base_url
        self._cache: dict = {}

    async def get_price(self, asset: str = "BTC") -> Optional[SpotPrice]:
        index_id = self.ASSET_INDEX_MAP.get(asset.upper())
        if not index_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/summary",
                    params={"id": index_id}
                )
                response.raise_for_status()
                data = response.json()

                payload = data.get("payload", {})
                price = SpotPrice(
                    asset=asset.upper(),
                    price=float(payload.get("value", 0)),
                    timestamp=datetime.now(timezone.utc)
                )
                self._cache[asset] = price
                return price
        except Exception as e:
            print(f"Spot price error: {e}")
            return self._cache.get(asset)
