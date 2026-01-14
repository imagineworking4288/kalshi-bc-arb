import httpx
import asyncio
import random
import time
import uuid
from typing import Optional, List, Dict, Any
from ..config import get_settings
from ..utils.kalshi_auth import KalshiAuth
from .log_config import get_logger

logger = get_logger("kalshi_client")


class RateLimiter:
    """
    Simple token bucket rate limiter for API requests.

    Limits requests to max_requests per window_seconds.
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 1.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            now = time.time()
            # Remove old requests outside the window
            self.requests = [t for t in self.requests if now - t < self.window_seconds]

            if len(self.requests) >= self.max_requests:
                # Wait until oldest request expires
                wait_time = self.window_seconds - (now - self.requests[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Clean up again after waiting
                    now = time.time()
                    self.requests = [t for t in self.requests if now - t < self.window_seconds]

            self.requests.append(time.time())


class KalshiClient:
    """Client for Kalshi REST API with rate limiting and idempotency support."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.kalshi_base_url
        self.auth: Optional[KalshiAuth] = None

        if self.settings.has_kalshi_credentials:
            self.auth = KalshiAuth(
                self.settings.kalshi_api_key_id,
                self.settings.kalshi_private_key_path
            )

        # Rate limiters (Kalshi Free tier: 10 req/sec for both reads and writes)
        self._read_limiter = RateLimiter(max_requests=10, window_seconds=1.0)
        self._write_limiter = RateLimiter(max_requests=10, window_seconds=1.0)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make authenticated HTTP request with retry logic for 429/5xx errors.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json: JSON body
            max_retries: Maximum number of retry attempts

        Returns:
            JSON response as dict

        Raises:
            httpx.HTTPStatusError: On 4xx errors (except 429)
            Exception: After max retries exhausted
        """
        # Apply rate limiting
        if method.upper() in ("POST", "PUT", "DELETE"):
            await self._write_limiter.acquire()
        else:
            await self._read_limiter.acquire()

        url = f"{self.base_url}{endpoint}"
        path = f"/trade-api/v2{endpoint}"

        headers = {}
        if self.auth:
            headers = self.auth.get_headers(method, path)

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        headers=headers
                    )

                    # Retry on rate limit or server errors
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(
                                f"[Retry] {response.status_code} on {method} {endpoint} - "
                                f"waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            continue

                    response.raise_for_status()
                    return response.json() if response.content else {}

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"[Retry] Timeout on {method} {endpoint} - "
                        f"waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise

        raise Exception(f"Request to {endpoint} failed after {max_retries} attempts")

    # Market Data
    async def get_markets(self, limit: int = 1000) -> List[Dict]:
        """Fetch markets from Kalshi API."""
        result = await self._request("GET", "/markets", params={"limit": limit})
        return result.get("markets", [])

    async def get_market(self, ticker: str) -> Dict:
        """Get single market by ticker."""
        result = await self._request("GET", f"/markets/{ticker}")
        return result.get("market", {})

    async def get_orderbook(self, ticker: str, depth: int = 10) -> Dict:
        """Get orderbook for a market."""
        result = await self._request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth})
        return result.get("orderbook", {})

    async def get_events(
        self,
        series_ticker: Optional[str] = None,
        status: str = "open",
        with_nested_markets: bool = True,
        limit: int = 100
    ) -> List[Dict]:
        """
        Fetch events with optional nested market data.

        Args:
            series_ticker: Filter by series (e.g., "KXBTC")
            status: "open", "closed", or "settled"
            with_nested_markets: Include full market objects
            limit: Max results (1-200)

        Returns:
            List of event objects. Key field: "mutually_exclusive" (bool)
            indicates if exactly one market will resolve YES.
        """
        params = {"limit": limit, "status": status}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if with_nested_markets:
            params["with_nested_markets"] = "true"

        result = await self._request("GET", "/events", params=params)
        return result.get("events", [])

    # Account
    async def get_balance(self) -> Dict:
        """Get account balance."""
        return await self._request("GET", "/portfolio/balance")

    async def get_positions(self, status: str = "open") -> List[Dict]:
        """Get portfolio positions."""
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
        order_type: str = "limit",
        client_order_id: Optional[str] = None
    ) -> Dict:
        """
        Place a single order with idempotency support.

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            action: "buy" or "sell"
            count: Number of contracts
            price: Price in cents (1-99)
            order_type: "limit" or "market"
            client_order_id: Optional idempotency key (auto-generated if None)

        Returns:
            Order response from API
        """
        payload = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type,
            "client_order_id": client_order_id or str(uuid.uuid4())
        }
        payload["yes_price" if side == "yes" else "no_price"] = price

        try:
            return await self._request("POST", "/portfolio/orders", json=payload)
        except httpx.HTTPStatusError as e:
            # Log detailed error for debugging
            logger.error(
                f"Order failed: {e.response.status_code} - {e.response.text}"
            )
            raise

    async def place_batch_orders(self, orders: List[Dict]) -> Dict:
        """
        Execute multiple orders atomically via Kalshi's batch endpoint.

        Args:
            orders: List of order dicts, each containing:
                - ticker: str (market ticker)
                - side: str ("yes" or "no")
                - action: str ("buy" or "sell")
                - count: int (number of contracts)
                - yes_price: int (price in cents, 1-99)
                - client_order_id: (optional) idempotency key

        Returns:
            API response with "orders" list containing results for each order.
            Each result has "order" (if successful) or "error" (if failed).
        """
        # Add idempotency keys to orders that don't have them
        for order in orders:
            if "client_order_id" not in order:
                order["client_order_id"] = str(uuid.uuid4())

        try:
            return await self._request(
                "POST",
                "/portfolio/orders/batched",
                json={"orders": orders}
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Batch order failed: {e.response.status_code} - {e.response.text}"
            )
            raise

    async def get_fills(self, limit: int = 100) -> List[Dict]:
        """
        Get fill history from Kalshi API.

        Args:
            limit: Maximum fills to return (default 100)

        Returns:
            List of fill objects with trade_id, ticker, side, count, price, etc.
        """
        result = await self._request("GET", "/portfolio/fills", params={"limit": limit})
        return result.get("fills", [])

    async def get_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Get order history from Kalshi API.

        Args:
            status: Filter by status ("resting", "canceled", "executed")
            limit: Maximum orders to return (default 100)

        Returns:
            List of order objects
        """
        params = {"limit": limit}
        if status:
            params["status"] = status
        result = await self._request("GET", "/portfolio/orders", params=params)
        return result.get("orders", [])
