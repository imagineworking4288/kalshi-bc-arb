"""
Risk management for trading.
Enforces position limits, daily loss limits, and exposure controls.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_position_per_market: int = 100  # Max contracts per market
    max_total_position: int = 500  # Max total contracts across all markets
    max_daily_loss_cents: int = 5000  # $50 max daily loss
    max_single_trade_cents: int = 1000  # $10 max single trade
    max_open_positions: int = 10  # Max number of open positions
    max_exposure_percent: float = 25.0  # Max % of bankroll at risk


@dataclass
class RiskCheck:
    """Result of a risk check."""
    approved: bool
    reason: str
    adjusted_size: Optional[int] = None  # Suggested reduced size if applicable


@dataclass
class PositionState:
    """Track position state for a single market."""
    ticker: str
    contracts: int = 0
    avg_price_cents: int = 0
    total_cost_cents: int = 0
    unrealized_pnl_cents: int = 0


class RiskManager:
    """
    Manages trading risk by enforcing limits.

    Checks performed before each trade:
    - Daily loss limit
    - Per-market position limit
    - Total position limit
    - Single trade size limit
    - Exposure percentage limit
    - Open position count limit
    """

    def __init__(self, db, limits: Optional[RiskLimits] = None):
        """
        Initialize risk manager.

        Args:
            db: Database connection
            limits: Risk limits configuration
        """
        self.db = db
        self.limits = limits or RiskLimits()

        # In-memory tracking (synced with DB periodically)
        self._positions: Dict[str, PositionState] = {}
        self._daily_pnl_cents: int = 0
        self._daily_trades: int = 0
        self._current_date: date = date.today()

        # Thread safety
        self._lock = asyncio.Lock()

    async def check_trade(
        self,
        ticker: str,
        contracts: int,
        price_cents: int,
        balance_cents: int
    ) -> RiskCheck:
        """
        Check if a trade is allowed under risk limits.

        Args:
            ticker: Market ticker
            contracts: Number of contracts to trade
            price_cents: Price per contract in cents
            balance_cents: Current account balance in cents

        Returns:
            RiskCheck with approval status and reason
        """
        async with self._lock:
            # Reset daily tracking if new day
            await self._check_daily_reset()

            trade_cost = contracts * price_cents

            # Check 1: Daily loss limit
            if self._daily_pnl_cents < -self.limits.max_daily_loss_cents:
                return RiskCheck(
                    approved=False,
                    reason=f"Daily loss limit reached: {self._daily_pnl_cents}¢ "
                           f"(limit: -{self.limits.max_daily_loss_cents}¢)"
                )

            # Check 2: Single trade size
            if trade_cost > self.limits.max_single_trade_cents:
                # Calculate adjusted size
                adjusted = self.limits.max_single_trade_cents // price_cents
                if adjusted >= 1:
                    return RiskCheck(
                        approved=True,
                        reason=f"Trade reduced from {contracts} to {adjusted} contracts "
                               f"(max trade size: {self.limits.max_single_trade_cents}¢)",
                        adjusted_size=adjusted
                    )
                else:
                    return RiskCheck(
                        approved=False,
                        reason=f"Trade cost {trade_cost}¢ exceeds limit "
                               f"({self.limits.max_single_trade_cents}¢)"
                    )

            # Check 3: Per-market position limit
            current_position = self._positions.get(ticker, PositionState(ticker=ticker))
            new_position = current_position.contracts + contracts

            if new_position > self.limits.max_position_per_market:
                available = self.limits.max_position_per_market - current_position.contracts
                if available >= 1:
                    return RiskCheck(
                        approved=True,
                        reason=f"Position reduced from {contracts} to {available} contracts "
                               f"(max per market: {self.limits.max_position_per_market})",
                        adjusted_size=available
                    )
                else:
                    return RiskCheck(
                        approved=False,
                        reason=f"Position limit reached for {ticker}: "
                               f"{current_position.contracts}/{self.limits.max_position_per_market}"
                    )

            # Check 4: Total position limit
            total_position = sum(p.contracts for p in self._positions.values())
            new_total = total_position + contracts

            if new_total > self.limits.max_total_position:
                available = self.limits.max_total_position - total_position
                if available >= 1:
                    return RiskCheck(
                        approved=True,
                        reason=f"Trade reduced from {contracts} to {available} contracts "
                               f"(total position limit: {self.limits.max_total_position})",
                        adjusted_size=available
                    )
                else:
                    return RiskCheck(
                        approved=False,
                        reason=f"Total position limit reached: "
                               f"{total_position}/{self.limits.max_total_position}"
                    )

            # Check 5: Exposure percentage
            total_exposure = sum(p.total_cost_cents for p in self._positions.values())
            new_exposure = total_exposure + trade_cost
            exposure_percent = (new_exposure / balance_cents * 100) if balance_cents > 0 else 0

            if exposure_percent > self.limits.max_exposure_percent:
                # Calculate max allowed trade
                max_exposure = int(balance_cents * self.limits.max_exposure_percent / 100)
                available_exposure = max_exposure - total_exposure
                adjusted = available_exposure // price_cents if price_cents > 0 else 0

                if adjusted >= 1:
                    return RiskCheck(
                        approved=True,
                        reason=f"Trade reduced to {adjusted} contracts "
                               f"(exposure limit: {self.limits.max_exposure_percent}%)",
                        adjusted_size=adjusted
                    )
                else:
                    return RiskCheck(
                        approved=False,
                        reason=f"Exposure limit reached: {exposure_percent:.1f}% "
                               f"(limit: {self.limits.max_exposure_percent}%)"
                    )

            # Check 6: Open position count
            open_positions = len([p for p in self._positions.values() if p.contracts > 0])
            is_new_position = ticker not in self._positions or self._positions[ticker].contracts == 0

            if is_new_position and open_positions >= self.limits.max_open_positions:
                return RiskCheck(
                    approved=False,
                    reason=f"Max open positions reached: "
                           f"{open_positions}/{self.limits.max_open_positions}"
                )

            # All checks passed
            return RiskCheck(
                approved=True,
                reason="All risk checks passed"
            )

    async def record_trade(
        self,
        ticker: str,
        contracts: int,
        price_cents: int,
        pnl_cents: int = 0
    ) -> None:
        """
        Record a trade for risk tracking.

        Args:
            ticker: Market ticker
            contracts: Contracts traded (positive for buy, negative for sell)
            price_cents: Price per contract
            pnl_cents: Realized P&L (for exits)
        """
        async with self._lock:
            # Update position
            if ticker not in self._positions:
                self._positions[ticker] = PositionState(ticker=ticker)

            position = self._positions[ticker]
            position.contracts += contracts
            position.total_cost_cents += contracts * price_cents

            # Update average price
            if position.contracts > 0 and contracts > 0:
                # Simple average for now
                position.avg_price_cents = position.total_cost_cents // position.contracts

            # Clean up closed positions
            if position.contracts <= 0:
                del self._positions[ticker]

            # Update daily P&L
            self._daily_pnl_cents += pnl_cents
            self._daily_trades += 1

            logger.info(
                f"Recorded trade: {ticker} {contracts:+d} @ {price_cents}¢ "
                f"pnl={pnl_cents}¢ daily={self._daily_pnl_cents}¢"
            )

    async def record_pnl(self, pnl_cents: int) -> None:
        """Record P&L without position change (for settlements)."""
        async with self._lock:
            self._daily_pnl_cents += pnl_cents
            logger.info(f"Recorded P&L: {pnl_cents}¢ (daily total: {self._daily_pnl_cents}¢)")

    async def close_position(self, ticker: str, pnl_cents: int) -> None:
        """Close a position and record P&L."""
        async with self._lock:
            if ticker in self._positions:
                del self._positions[ticker]
            self._daily_pnl_cents += pnl_cents

    def get_status(self) -> dict:
        """Get current risk status for dashboard."""
        total_contracts = sum(p.contracts for p in self._positions.values())
        total_exposure = sum(p.total_cost_cents for p in self._positions.values())
        open_positions = len([p for p in self._positions.values() if p.contracts > 0])

        return {
            "limits": {
                "max_position_per_market": self.limits.max_position_per_market,
                "max_total_position": self.limits.max_total_position,
                "max_daily_loss_cents": self.limits.max_daily_loss_cents,
                "max_single_trade_cents": self.limits.max_single_trade_cents,
                "max_open_positions": self.limits.max_open_positions,
                "max_exposure_percent": self.limits.max_exposure_percent
            },
            "current": {
                "daily_pnl_cents": self._daily_pnl_cents,
                "daily_trades": self._daily_trades,
                "total_contracts": total_contracts,
                "total_exposure_cents": total_exposure,
                "open_positions": open_positions
            },
            "positions": {
                ticker: {
                    "contracts": p.contracts,
                    "avg_price_cents": p.avg_price_cents,
                    "total_cost_cents": p.total_cost_cents
                }
                for ticker, p in self._positions.items()
            },
            "daily_loss_remaining_cents": self.limits.max_daily_loss_cents + self._daily_pnl_cents
        }

    async def _check_daily_reset(self) -> None:
        """Reset daily tracking if it's a new day."""
        today = date.today()
        if today != self._current_date:
            logger.info(f"New trading day: resetting daily P&L from {self._daily_pnl_cents}¢")
            self._daily_pnl_cents = 0
            self._daily_trades = 0
            self._current_date = today

    async def sync_positions(self, positions: list) -> None:
        """
        Sync in-memory positions with external source.

        Args:
            positions: List of position dicts with ticker, contracts, etc.
        """
        async with self._lock:
            self._positions.clear()
            for pos in positions:
                ticker = pos.get("ticker")
                if ticker and pos.get("contracts", 0) > 0:
                    self._positions[ticker] = PositionState(
                        ticker=ticker,
                        contracts=pos.get("contracts", 0),
                        avg_price_cents=int(pos.get("avg_price", 0) * 100),
                        total_cost_cents=int(pos.get("total_cost", 0) * 100)
                    )
            logger.info(f"Synced {len(self._positions)} positions")
