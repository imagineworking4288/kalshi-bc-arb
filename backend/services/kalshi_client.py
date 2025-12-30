import httpx
from typing import Optional, List, Dict, Any
from ..config import get_settings
from ..utils.kalshi_auth import KalshiAuth


class KalshiClient:
    """Client for Kalshi REST API"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.kalshi_api_url
        self.auth: Optional[KalshiAuth] = None

        if self.settings.has_kalshi_credentials:
            self.auth = KalshiAuth(
                self.settings.kalshi_api_key_id,
                self.settings.kalshi_private_key_path
            )

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        path = f"/trade-api/v2{endpoint}"

        headers = {}
        if self.auth:
            headers = self.auth.get_headers(method, path)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=headers
            )
            response.raise_for_status()
            return response.json() if response.content else {}

    # Market Data
    async def get_markets(self, status: str = "active", limit: int = 1000) -> List[Dict]:
        result = await self._request("GET", "/markets", params={"status": status, "limit": limit})
        return result.get("markets", [])

    async def get_market(self, ticker: str) -> Dict:
        result = await self._request("GET", f"/markets/{ticker}")
        return result.get("market", {})

    async def get_orderbook(self, ticker: str, depth: int = 10) -> Dict:
        result = await self._request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth})
        return result.get("orderbook", {})

    # Account
    async def get_balance(self) -> Dict:
        return await self._request("GET", "/portfolio/balance")

    async def get_positions(self, status: str = "open") -> List[Dict]:
        result = await self._request("GET", "/portfolio/positions", params={"status": status})
        return result.get("positions", [])

    # Orders
    async def place_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        price: int,
        order_type: str = "limit"
    ) -> Dict:
        payload = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type
        }
        payload["yes_price" if side == "yes" else "no_price"] = price
        return await self._request("POST", "/portfolio/orders", json=payload)
