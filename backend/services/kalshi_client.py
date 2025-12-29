"""Kalshi API client for market data and trading"""

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from ..config import get_settings
from ..utils.auth import KalshiAuth
from ..utils.errors import (
    AuthenticationError,
    InsufficientBalanceError,
    KalshiError,
    MarketClosedError,
    OrderError,
    RateLimitError,
)


class KalshiClient:
    """Async HTTP client for Kalshi API"""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.kalshi_api_url
        self.auth = KalshiAuth(
            settings.kalshi_api_key_id,
            settings.kalshi_private_key_path
        )
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limit_remaining = 100
        self._rate_limit_reset = 0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Kalshi API.

        Args:
            method: HTTP method
            path: API endpoint path
            **kwargs: Additional arguments to pass to httpx

        Returns:
            JSON response as dictionary

        Raises:
            KalshiError: On API errors
        """
        client = await self._get_client()

        # Build full path for signing
        full_path = f"/trade-api/v2{path}"
        headers = self.auth.get_auth_headers(method, full_path)
        headers["Content-Type"] = "application/json"

        try:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                **kwargs
            )

            # Track rate limits
            if "X-RateLimit-Remaining" in response.headers:
                self._rate_limit_remaining = int(
                    response.headers["X-RateLimit-Remaining"]
                )
            if "X-RateLimit-Reset" in response.headers:
                self._rate_limit_reset = int(
                    response.headers["X-RateLimit-Reset"]
                )

            # Handle errors
            if response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed",
                    status_code=401,
                    response=response.json() if response.content else None
                )
            elif response.status_code == 429:
                raise RateLimitError(
                    "Rate limit exceeded",
                    status_code=429,
                    response=response.json() if response.content else None
                )
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise KalshiError(
                    error_data.get("message", f"API error: {response.status_code}"),
                    status_code=response.status_code,
                    response=error_data
                )

            return response.json() if response.content else {}

        except httpx.HTTPError as e:
            raise KalshiError(f"HTTP error: {str(e)}")

    # Market endpoints

    async def get_markets(
        self,
        status: str = "active",
        series_ticker: Optional[str] = None,
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch markets with given status.

        Args:
            status: Market status filter (active, closed, settled)
            series_ticker: Filter by series
            limit: Maximum number of markets to return
            cursor: Pagination cursor

        Returns:
            List of market dictionaries
        """
        params = {"status": status, "limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if cursor:
            params["cursor"] = cursor

        result = await self._request("GET", "/markets", params=params)
        return result.get("markets", [])

    async def get_market(self, ticker: str) -> Dict:
        """
        Fetch a single market by ticker.

        Args:
            ticker: Market ticker

        Returns:
            Market dictionary
        """
        result = await self._request("GET", f"/markets/{ticker}")
        return result.get("market", {})

    async def get_orderbook(self, ticker: str, depth: int = 10) -> Dict:
        """
        Fetch orderbook for a specific market.

        Args:
            ticker: Market ticker
            depth: Number of levels to fetch

        Returns:
            Orderbook dictionary with 'yes' and 'no' sides
        """
        result = await self._request(
            "GET",
            f"/markets/{ticker}/orderbook",
            params={"depth": depth}
        )
        return result.get("orderbook", {})

    async def get_series(self, series_ticker: str) -> Dict:
        """
        Fetch series information.

        Args:
            series_ticker: Series ticker

        Returns:
            Series dictionary
        """
        result = await self._request("GET", f"/series/{series_ticker}")
        return result.get("series", {})

    # Portfolio endpoints

    async def get_balance(self) -> Dict:
        """
        Fetch account balance.

        Returns:
            Balance dictionary with 'available_balance' and 'total_balance' in cents
        """
        return await self._request("GET", "/portfolio/balance")

    async def get_positions(
        self,
        ticker: Optional[str] = None,
        settlement_status: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch open positions.

        Args:
            ticker: Filter by market ticker
            settlement_status: Filter by settlement status

        Returns:
            List of position dictionaries
        """
        params = {}
        if ticker:
            params["ticker"] = ticker
        if settlement_status:
            params["settlement_status"] = settlement_status

        result = await self._request(
            "GET",
            "/portfolio/positions",
            params=params
        )
        return result.get("market_positions", [])

    async def get_orders(
        self,
        ticker: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch orders.

        Args:
            ticker: Filter by market ticker
            status: Filter by order status

        Returns:
            List of order dictionaries
        """
        params = {}
        if ticker:
            params["ticker"] = ticker
        if status:
            params["status"] = status

        result = await self._request("GET", "/portfolio/orders", params=params)
        return result.get("orders", [])

    # Trading endpoints

    async def place_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        price: int,
        order_type: str = "limit",
        client_order_id: Optional[str] = None
    ) -> Dict:
        """
        Place an order.

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            action: "buy" or "sell"
            count: Number of contracts
            price: Price in cents (1-99)
            order_type: "limit" or "market"
            client_order_id: Optional client-provided order ID

        Returns:
            Order result dictionary
        """
        payload = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type,
        }

        if side == "yes":
            payload["yes_price"] = price
        else:
            payload["no_price"] = price

        if client_order_id:
            payload["client_order_id"] = client_order_id

        try:
            result = await self._request(
                "POST",
                "/portfolio/orders",
                json=payload
            )
            return result
        except KalshiError as e:
            # Convert specific errors
            if e.response:
                error_code = e.response.get("error_code", "")
                if "insufficient" in error_code.lower():
                    raise InsufficientBalanceError(
                        e.message,
                        status_code=e.status_code,
                        response=e.response
                    )
                if "closed" in error_code.lower():
                    raise MarketClosedError(
                        e.message,
                        status_code=e.status_code,
                        response=e.response
                    )
            raise OrderError(
                e.message,
                status_code=e.status_code,
                response=e.response
            )

    async def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation result
        """
        return await self._request(
            "DELETE",
            f"/portfolio/orders/{order_id}"
        )

    async def batch_place_orders(
        self,
        orders: List[Dict]
    ) -> Dict:
        """
        Place multiple orders atomically.

        Args:
            orders: List of order dictionaries

        Returns:
            Batch result dictionary
        """
        return await self._request(
            "POST",
            "/portfolio/orders/batched",
            json={"orders": orders}
        )

    # Utility methods

    @property
    def is_authenticated(self) -> bool:
        """Check if client is configured with authentication"""
        return self.auth.is_configured

    @property
    def rate_limit_remaining(self) -> int:
        """Get remaining rate limit"""
        return self._rate_limit_remaining
