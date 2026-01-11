"""
Unified Position Manager for Kalshi Trading Platform.

Provides a single interface for position tracking across paper and live modes
with caching to reduce API calls and consistent position representation.

Key Features:
- Unified position model (UnifiedPosition dataclass)
- TTL-based caching for live positions (reduces API calls)
- Thread-safe operations with asyncio.Lock
- Position constraint validation (Kalshi doesn't allow YES+NO on same market)
- Exposure calculation and aggregation

Usage:
    from backend.services.core import PositionManager, PositionConfig

    manager = PositionManager(
        kalshi_client=client,
        db=database,
        config=PositionConfig(cache_ttl_seconds=30)
    )

    # Get all positions
    positions = await manager.get_positions(mode="paper")

    # Check specific position
    position = await manager.get_position("KXBTC-24DEC31-100000", mode="live")

    # Check if position exists
    has_pos = await manager.has_position("KXBTC-24DEC31-100000", mode="paper")

    # Get total exposure
    exposure = await manager.get_exposure(mode="paper")
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from ..log_config import get_logger

logger = get_logger("position_manager")


class PositionSource(str, Enum):
    """Source of position data."""

    PAPER = "paper"  # SQLite paper_positions table
    LIVE = "live"  # Kalshi API
    BOTH = "both"  # Aggregated from both sources


@dataclass
class PositionConfig:
    """
    Configuration for PositionManager behavior.

    Attributes:
        cache_ttl_seconds: How long to cache live positions (default 30s)
        max_cache_entries: Maximum positions to cache (default 500)
        enable_caching: Whether to cache live positions (default True)
        auto_refresh: Whether to auto-refresh expired cache on access (default True)
    """

    cache_ttl_seconds: int = 30
    max_cache_entries: int = 500
    enable_caching: bool = True
    auto_refresh: bool = True


@dataclass
class UnifiedPosition:
    """
    Unified position representation across paper and live modes.

    This dataclass normalizes the different formats from paper_positions table
    and Kalshi API into a consistent structure.

    Attributes:
        ticker: Market ticker (e.g., "KXBTC-24DEC31-100000")
        side: Position side ("yes" or "no")
        contracts: Number of contracts held (always positive)
        avg_price_cents: Average entry price in cents
        total_cost_cents: Total cost basis in cents
        total_fees_cents: Total fees paid in cents
        unrealized_pnl_cents: Unrealized P&L in cents (if market price available)
        source: Where this position came from (paper, live, or both)
        created_at: When position was opened
        market_exposure_cents: Current market exposure (contracts * current_price)
        settlement_time: When the market settles (if available)
        metadata: Additional source-specific data
    """

    ticker: str
    side: str  # "yes" or "no"
    contracts: int
    avg_price_cents: int
    total_cost_cents: int
    total_fees_cents: int = 0
    unrealized_pnl_cents: int = 0
    source: PositionSource = PositionSource.PAPER
    created_at: Optional[datetime] = None
    market_exposure_cents: int = 0
    settlement_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CachedPositions:
    """Cached position data with timestamp for TTL."""

    positions: Dict[str, UnifiedPosition]
    cached_at: datetime


@dataclass
class ExposureSummary:
    """
    Summary of portfolio exposure.

    Attributes:
        total_exposure_cents: Total value at risk
        position_count: Number of open positions
        total_cost_cents: Sum of all position costs
        total_fees_cents: Sum of all fees paid
        by_side: Breakdown by yes/no side
        by_ticker: Breakdown by market ticker
    """

    total_exposure_cents: int
    position_count: int
    total_cost_cents: int
    total_fees_cents: int
    by_side: Dict[str, int]
    by_ticker: Dict[str, int]


class PositionManager:
    """
    Unified position tracking across paper and live modes.

    This manager provides a single interface for querying positions from
    both paper trading (SQLite) and live trading (Kalshi API) with:
    - Consistent position representation (UnifiedPosition)
    - TTL-based caching for live positions to reduce API calls
    - Thread-safe operations
    - Position constraint validation

    Thread Safety:
        All methods are async-safe and use asyncio.Lock for critical sections.

    Caching Strategy:
        Live positions are cached for configurable TTL (default 30s).
        Paper positions are always fetched fresh from SQLite (fast).
    """

    def __init__(
        self,
        kalshi_client,  # KalshiClient
        db,  # Database connection
        config: Optional[PositionConfig] = None,
    ):
        """
        Initialize PositionManager with dependencies.

        Args:
            kalshi_client: KalshiClient instance for live position fetching
            db: Database instance for paper position queries
            config: Optional configuration overrides
        """
        self.kalshi_client = kalshi_client
        self.db = db
        self.config = config or PositionConfig()

        # Cache for live positions
        self._live_cache: Optional[CachedPositions] = None

        # Thread safety
        self._lock = asyncio.Lock()

        logger.info(
            f"PositionManager initialized: cache_ttl={self.config.cache_ttl_seconds}s, "
            f"caching={'enabled' if self.config.enable_caching else 'disabled'}"
        )

    async def get_positions(
        self,
        mode: str = "paper",
        force_refresh: bool = False,
    ) -> List[UnifiedPosition]:
        """
        Get all positions for the specified mode.

        Args:
            mode: "paper", "live", or "both"
            force_refresh: Force cache refresh for live positions

        Returns:
            List of UnifiedPosition objects

        Raises:
            ValueError: If mode is invalid
        """
        if mode not in ("paper", "live", "both"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'paper', 'live', or 'both'")

        positions: List[UnifiedPosition] = []

        if mode in ("paper", "both"):
            paper_positions = await self._fetch_paper_positions()
            positions.extend(paper_positions)

        if mode in ("live", "both"):
            live_positions = await self._fetch_live_positions(force_refresh)
            positions.extend(live_positions)

        logger.debug(f"get_positions({mode}): {len(positions)} positions")
        return positions

    async def get_position(
        self,
        ticker: str,
        mode: str = "paper",
        force_refresh: bool = False,
    ) -> Optional[UnifiedPosition]:
        """
        Get position for a specific ticker.

        Args:
            ticker: Market ticker
            mode: "paper", "live", or "both" (returns first found)
            force_refresh: Force cache refresh for live positions

        Returns:
            UnifiedPosition if found, None otherwise
        """
        positions = await self.get_positions(mode, force_refresh)

        for pos in positions:
            if pos.ticker == ticker:
                return pos

        return None

    async def has_position(
        self,
        ticker: str,
        mode: str = "paper",
        side: Optional[str] = None,
    ) -> bool:
        """
        Check if a position exists for a ticker.

        Args:
            ticker: Market ticker
            mode: "paper", "live", or "both"
            side: Optional side filter ("yes" or "no")

        Returns:
            True if position exists (optionally matching side)
        """
        position = await self.get_position(ticker, mode)

        if position is None:
            return False

        if side is not None:
            return position.side == side

        return True

    async def can_open_position(
        self,
        ticker: str,
        side: str,
        mode: str = "paper",
    ) -> Tuple[bool, str]:
        """
        Check if a new position can be opened.

        IMPORTANT: Kalshi does NOT allow holding YES and NO on the same market
        simultaneously. This method validates that constraint.

        Args:
            ticker: Market ticker
            side: Desired side ("yes" or "no")
            mode: Trading mode

        Returns:
            Tuple of (can_open, reason)
        """
        existing = await self.get_position(ticker, mode)

        if existing is None:
            return True, "No existing position"

        if existing.side == side:
            return True, f"Same side position exists ({existing.contracts} contracts)"

        # Opposite side position exists - cannot open
        return False, (
            f"Cannot open {side.upper()} position: "
            f"existing {existing.side.upper()} position with {existing.contracts} contracts. "
            f"Kalshi does not allow YES and NO positions on the same market."
        )

    async def get_exposure(
        self,
        mode: str = "paper",
    ) -> ExposureSummary:
        """
        Get total portfolio exposure summary.

        Args:
            mode: "paper", "live", or "both"

        Returns:
            ExposureSummary with aggregated exposure data
        """
        positions = await self.get_positions(mode)

        total_exposure = 0
        total_cost = 0
        total_fees = 0
        by_side: Dict[str, int] = {"yes": 0, "no": 0}
        by_ticker: Dict[str, int] = {}

        for pos in positions:
            exposure = pos.market_exposure_cents or pos.total_cost_cents
            total_exposure += exposure
            total_cost += pos.total_cost_cents
            total_fees += pos.total_fees_cents

            by_side[pos.side] = by_side.get(pos.side, 0) + exposure
            by_ticker[pos.ticker] = by_ticker.get(pos.ticker, 0) + exposure

        return ExposureSummary(
            total_exposure_cents=total_exposure,
            position_count=len(positions),
            total_cost_cents=total_cost,
            total_fees_cents=total_fees,
            by_side=by_side,
            by_ticker=by_ticker,
        )

    async def get_positions_by_ticker_prefix(
        self,
        prefix: str,
        mode: str = "paper",
    ) -> List[UnifiedPosition]:
        """
        Get positions matching a ticker prefix.

        Useful for finding all positions in a series (e.g., "KXBTC-24DEC31").

        Args:
            prefix: Ticker prefix to match
            mode: Trading mode

        Returns:
            List of matching positions
        """
        positions = await self.get_positions(mode)
        return [p for p in positions if p.ticker.startswith(prefix)]

    async def get_position_count(
        self,
        mode: str = "paper",
    ) -> int:
        """
        Get count of open positions.

        Args:
            mode: Trading mode

        Returns:
            Number of open positions
        """
        positions = await self.get_positions(mode)
        return len([p for p in positions if p.contracts > 0])

    async def _fetch_paper_positions(self) -> List[UnifiedPosition]:
        """
        Fetch positions from paper_positions table.

        Paper positions are always fetched fresh (SQLite is fast).

        Returns:
            List of UnifiedPosition objects from paper trading
        """
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT
                        ticker, side, contracts, avg_price, total_cost,
                        total_fees, created_at, settlement_time
                    FROM paper_positions
                    WHERE settled = 0 AND contracts > 0
                """
                )
                rows = await cursor.fetchall()

                positions = []
                for row in rows:
                    # Paper positions store prices in dollars, convert to cents
                    avg_price_cents = int(float(row[3] or 0) * 100)
                    total_cost_cents = int(float(row[4] or 0) * 100)
                    total_fees_cents = int(float(row[5] or 0) * 100)

                    # Parse timestamps
                    created_at = None
                    if row[6]:
                        try:
                            created_at = datetime.fromisoformat(
                                str(row[6]).replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            pass

                    settlement_time = None
                    if row[7]:
                        try:
                            settlement_time = datetime.fromisoformat(
                                str(row[7]).replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            pass

                    positions.append(
                        UnifiedPosition(
                            ticker=row[0],
                            side=row[1],
                            contracts=row[2],
                            avg_price_cents=avg_price_cents,
                            total_cost_cents=total_cost_cents,
                            total_fees_cents=total_fees_cents,
                            source=PositionSource.PAPER,
                            created_at=created_at,
                            market_exposure_cents=total_cost_cents,  # Use cost as exposure
                            settlement_time=settlement_time,
                        )
                    )

                logger.debug(f"Fetched {len(positions)} paper positions")
                return positions

        except Exception as e:
            logger.error(f"Failed to fetch paper positions: {e}")
            return []

    async def _fetch_live_positions(
        self,
        force_refresh: bool = False,
    ) -> List[UnifiedPosition]:
        """
        Fetch positions from Kalshi API with caching.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of UnifiedPosition objects from live trading
        """
        async with self._lock:
            # Check cache validity
            if (
                self.config.enable_caching
                and not force_refresh
                and self._live_cache is not None
            ):
                age = (
                    datetime.now(timezone.utc) - self._live_cache.cached_at
                ).total_seconds()
                if age < self.config.cache_ttl_seconds:
                    logger.debug(f"Using cached live positions (age={age:.1f}s)")
                    return list(self._live_cache.positions.values())

            # Fetch fresh from API
            try:
                if not self.kalshi_client:
                    logger.warning("No Kalshi client configured for live positions")
                    return []

                api_positions = await self.kalshi_client.get_positions(status="open")

                positions: Dict[str, UnifiedPosition] = {}
                for pos in api_positions:
                    ticker = pos.get("ticker", "")
                    if not ticker:
                        continue

                    # Kalshi returns position as signed int (+YES, -NO)
                    position_count = pos.get("position", 0)
                    if position_count == 0:
                        continue

                    side = "yes" if position_count > 0 else "no"
                    contracts = abs(position_count)

                    # Kalshi returns exposure in cents
                    market_exposure_cents = pos.get("market_exposure", 0)
                    avg_price_cents = (
                        market_exposure_cents // contracts if contracts > 0 else 0
                    )

                    # Parse created time
                    created_at = None
                    created_str = pos.get("created_time")
                    if created_str:
                        try:
                            created_at = datetime.fromisoformat(
                                created_str.replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            pass

                    positions[ticker] = UnifiedPosition(
                        ticker=ticker,
                        side=side,
                        contracts=contracts,
                        avg_price_cents=avg_price_cents,
                        total_cost_cents=market_exposure_cents,
                        total_fees_cents=0,  # Kalshi doesn't expose fees per position
                        source=PositionSource.LIVE,
                        created_at=created_at,
                        market_exposure_cents=market_exposure_cents,
                        metadata={
                            "resting_orders_count": pos.get("resting_orders_count", 0),
                            "realized_pnl": pos.get("realized_pnl", 0),
                        },
                    )

                # Update cache
                if self.config.enable_caching:
                    self._live_cache = CachedPositions(
                        positions=positions,
                        cached_at=datetime.now(timezone.utc),
                    )

                logger.debug(f"Fetched {len(positions)} live positions")
                return list(positions.values())

            except Exception as e:
                logger.error(f"Failed to fetch live positions: {e}")
                # Return stale cache if available
                if self._live_cache is not None:
                    logger.warning("Returning stale cached positions due to API error")
                    return list(self._live_cache.positions.values())
                return []

    def invalidate_cache(self) -> None:
        """
        Invalidate the live position cache.

        Call this after executing trades to ensure fresh data on next query.
        """
        self._live_cache = None
        logger.debug("Live position cache invalidated")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status for monitoring dashboards.

        Returns:
            Dict with configuration and cache status
        """
        cache_age = None
        cache_size = 0
        if self._live_cache is not None:
            cache_age = (
                datetime.now(timezone.utc) - self._live_cache.cached_at
            ).total_seconds()
            cache_size = len(self._live_cache.positions)

        return {
            "config": {
                "cache_ttl_seconds": self.config.cache_ttl_seconds,
                "max_cache_entries": self.config.max_cache_entries,
                "enable_caching": self.config.enable_caching,
                "auto_refresh": self.config.auto_refresh,
            },
            "cache": {
                "has_cache": self._live_cache is not None,
                "cache_age_seconds": round(cache_age, 1) if cache_age else None,
                "cache_size": cache_size,
                "is_stale": (
                    cache_age > self.config.cache_ttl_seconds
                    if cache_age is not None
                    else None
                ),
            },
            "has_kalshi_client": self.kalshi_client is not None,
            "has_db": self.db is not None,
        }
