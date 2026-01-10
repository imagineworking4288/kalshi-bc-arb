"""
Pydantic models for Kalshi API data.
These models handle validation, serialization, and business logic.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum

from .types import MarketStatus, OrderSide, OrderAction, TimeInForce, OrderbookLevel


class OrderbookLevelModel(BaseModel):
    """Single level in orderbook"""
    price_cents: int = Field(ge=1, le=99)
    quantity: int = Field(ge=0)

    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100.0


class Orderbook(BaseModel):
    """
    Full orderbook for a market.

    CRITICAL: Kalshi only returns BIDS. To buy YES, you take from NO bids.
    - YES bid @ 60¢ = someone will pay 60¢ for YES
    - NO bid @ 45¢ = someone will pay 45¢ for NO
    - To BUY YES: Take NO bids, your price = 100 - NO_bid
    - To SELL YES: Take YES bids
    """
    ticker: str
    yes_bids: List[OrderbookLevelModel] = Field(default_factory=list)
    no_bids: List[OrderbookLevelModel] = Field(default_factory=list)
    sequence: int = Field(default=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def best_yes_bid(self) -> Optional[int]:
        """Best price someone will PAY for YES"""
        if not self.yes_bids:
            return None
        return max(level.price_cents for level in self.yes_bids)

    def best_no_bid(self) -> Optional[int]:
        """Best price someone will PAY for NO"""
        if not self.no_bids:
            return None
        return max(level.price_cents for level in self.no_bids)

    def yes_ask(self) -> Optional[int]:
        """
        Price to BUY YES = 100 - best NO bid
        (Taking from NO bidders)
        """
        best_no = self.best_no_bid()
        if best_no is None:
            return None
        return 100 - best_no

    def no_ask(self) -> Optional[int]:
        """
        Price to BUY NO = 100 - best YES bid
        (Taking from YES bidders)
        """
        best_yes = self.best_yes_bid()
        if best_yes is None:
            return None
        return 100 - best_yes

    def take_yes_cost(self, quantity: int) -> Dict[str, Any]:
        """
        Calculate cost to BUY `quantity` YES contracts.
        Takes liquidity from NO bids (sorted highest first = cheapest YES).
        """
        if not self.no_bids:
            return {'fillable': 0, 'total_cost_cents': 0, 'avg_price': None, 'fills': []}

        # Sort NO bids descending - highest NO bid = lowest YES ask
        sorted_bids = sorted(self.no_bids, key=lambda x: x.price_cents, reverse=True)

        remaining = quantity
        total_cost = 0
        fills = []

        for level in sorted_bids:
            if remaining <= 0:
                break

            yes_price = 100 - level.price_cents
            fill_qty = min(remaining, level.quantity)

            fills.append({
                'price_cents': yes_price,
                'quantity': fill_qty,
                'cost_cents': yes_price * fill_qty
            })

            total_cost += yes_price * fill_qty
            remaining -= fill_qty

        filled = quantity - remaining
        avg_price = total_cost / filled if filled > 0 else None

        return {
            'fillable': filled,
            'unfilled': remaining,
            'total_cost_cents': total_cost,
            'avg_price_cents': avg_price,
            'fills': fills
        }

    def take_no_cost(self, quantity: int) -> Dict[str, Any]:
        """
        Calculate cost to BUY `quantity` NO contracts.
        Takes liquidity from YES bids (sorted highest first = cheapest NO).
        """
        if not self.yes_bids:
            return {'fillable': 0, 'total_cost_cents': 0, 'avg_price': None, 'fills': []}

        # Sort YES bids descending - highest YES bid = lowest NO ask
        sorted_bids = sorted(self.yes_bids, key=lambda x: x.price_cents, reverse=True)

        remaining = quantity
        total_cost = 0
        fills = []

        for level in sorted_bids:
            if remaining <= 0:
                break

            no_price = 100 - level.price_cents
            fill_qty = min(remaining, level.quantity)

            fills.append({
                'price_cents': no_price,
                'quantity': fill_qty,
                'cost_cents': no_price * fill_qty
            })

            total_cost += no_price * fill_qty
            remaining -= fill_qty

        filled = quantity - remaining
        avg_price = total_cost / filled if filled > 0 else None

        return {
            'fillable': filled,
            'unfilled': remaining,
            'total_cost_cents': total_cost,
            'avg_price_cents': avg_price,
            'fills': fills
        }

    def yes_liquidity_at_price(self, max_price_cents: int) -> int:
        """Total YES contracts available at or below max_price"""
        total = 0
        for level in self.no_bids:
            yes_price = 100 - level.price_cents
            if yes_price <= max_price_cents:
                total += level.quantity
        return total

    def no_liquidity_at_price(self, max_price_cents: int) -> int:
        """Total NO contracts available at or below max_price"""
        total = 0
        for level in self.yes_bids:
            no_price = 100 - level.price_cents
            if no_price <= max_price_cents:
                total += level.quantity
        return total

    def is_stale(self, max_age_seconds: float = 5.0) -> bool:
        """Check if orderbook data is too old"""
        age = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return age > max_age_seconds


class Market(BaseModel):
    """
    Complete market data from Kalshi API.
    Handles 50+ fields with validation.
    """
    ticker: str
    event_ticker: str
    market_type: str = "binary"
    title: str
    subtitle: Optional[str] = None

    # Status
    status: MarketStatus
    result: Optional[str] = None  # "yes", "no", "all_yes", "all_no"

    # Pricing (cents)
    yes_bid: Optional[int] = Field(default=None, ge=0, le=100)
    yes_ask: Optional[int] = Field(default=None, ge=0, le=100)
    no_bid: Optional[int] = Field(default=None, ge=0, le=100)
    no_ask: Optional[int] = Field(default=None, ge=0, le=100)
    last_price: Optional[int] = Field(default=None, ge=0, le=100)

    # Previous prices (for change detection)
    previous_yes_bid: Optional[int] = None
    previous_yes_ask: Optional[int] = None
    previous_price: Optional[int] = None

    # Volume & Interest
    volume: int = 0
    volume_24h: int = 0
    open_interest: int = 0

    # Contract specs
    tick_size: int = 1
    notional_value: int = 100  # cents

    # Strike info (for bracket markets)
    strike_type: Optional[str] = None  # "greater", "less", "between"
    floor_strike: Optional[int] = None  # Integer degrees, NOT float
    cap_strike: Optional[int] = None
    functional_strike: Optional[str] = None  # e.g., ">=62"

    # Timestamps (all UTC)
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    expiration_time: Optional[datetime] = None

    # Settlement
    settlement_value: Optional[int] = None
    can_close_early: bool = False

    # Metadata
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('floor_strike', 'cap_strike', mode='before')
    @classmethod
    def convert_strike_to_int(cls, v):
        """Ensure strikes are integers (degrees F)"""
        if v is None:
            return None
        return int(v)

    @field_validator('open_time', 'close_time', 'expiration_time', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        """Parse ISO datetime strings to timezone-aware datetime"""
        if v is None:
            return None
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return v

    def is_open(self) -> bool:
        return self.status == MarketStatus.OPEN

    def is_tradeable(self) -> bool:
        return self.status in [MarketStatus.OPEN]

    def bracket_label(self) -> str:
        """Human-readable bracket description"""
        if self.floor_strike is not None and self.cap_strike is not None:
            return f"{self.floor_strike}-{self.cap_strike}°F"
        elif self.floor_strike is not None:
            return f"≥{self.floor_strike}°F"
        elif self.cap_strike is not None:
            return f"<{self.cap_strike}°F"
        return self.title

    def time_to_close(self) -> Optional[float]:
        """Seconds until market closes"""
        if self.close_time is None:
            return None
        delta = self.close_time - datetime.now(timezone.utc)
        return max(0, delta.total_seconds())

    def is_near_settlement(self, threshold_hours: float = 2.0) -> bool:
        """Check if market is close to settlement"""
        ttc = self.time_to_close()
        if ttc is None:
            return False
        return ttc < threshold_hours * 3600

    def data_age_seconds(self) -> float:
        """How old is this market data"""
        return (datetime.now(timezone.utc) - self.fetched_at).total_seconds()

    def is_stale(self, max_age_seconds: float = 30.0) -> bool:
        """Check if market data is too old for trading"""
        return self.data_age_seconds() > max_age_seconds


class Event(BaseModel):
    """
    Event containing multiple markets.
    For weather: one event per city per day with 6 bracket markets.
    """
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: Optional[str] = None
    category: str

    # Critical for arbitrage
    mutually_exclusive: bool = False

    # Timestamps
    strike_date: Optional[datetime] = None

    # Nested markets
    markets: List[Market] = Field(default_factory=list)

    def open_markets(self) -> List[Market]:
        """Get only tradeable markets"""
        return [m for m in self.markets if m.is_tradeable()]

    def total_yes_cost(self) -> Optional[int]:
        """Sum of all YES asks - for arbitrage detection"""
        markets = self.open_markets()
        if not markets:
            return None

        total = 0
        for m in markets:
            if m.yes_ask is None:
                return None  # Can't calculate if any missing
            total += m.yes_ask
        return total

    def total_no_cost(self) -> Optional[int]:
        """Sum of all NO asks - for N-1 arbitrage"""
        markets = self.open_markets()
        if not markets:
            return None

        total = 0
        for m in markets:
            if m.no_ask is None:
                return None
            total += m.no_ask
        return total

    def has_arbitrage_opportunity(self) -> bool:
        """Quick check if sum < 100 (before fees)"""
        if not self.mutually_exclusive:
            return False

        yes_cost = self.total_yes_cost()
        if yes_cost is not None and yes_cost < 100:
            return True

        # Also check if N-1 NO strategy works
        no_cost = self.total_no_cost()
        n = len(self.open_markets())
        if no_cost is not None and n > 1:
            # N-1 NO positions pay out (N-1) * 100 when one bracket wins
            # But we need to exclude the winning bracket, so max payout is (N-1)*100
            # This is complex - delegate to ArbitrageCalculator
            pass

        return False


class Position(BaseModel):
    """User's position in a market"""
    ticker: str
    event_ticker: Optional[str] = None

    # Position: positive = YES contracts, negative = NO contracts
    position: int = 0

    # Cost basis
    total_cost_cents: int = 0
    avg_cost_cents: float = 0.0

    # P&L
    realized_pnl_cents: int = 0
    fees_paid_cents: int = 0

    # Timestamps
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def side(self) -> Optional[str]:
        if self.position > 0:
            return "yes"
        elif self.position < 0:
            return "no"
        return None

    @property
    def quantity(self) -> int:
        return abs(self.position)

    def unrealized_pnl(self, current_price_cents: int) -> int:
        """Calculate unrealized P&L at current price"""
        if self.position == 0:
            return 0

        current_value = abs(self.position) * current_price_cents
        return current_value - self.total_cost_cents


class Order(BaseModel):
    """Order to be placed or existing order"""
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    ticker: str

    side: OrderSide
    action: OrderAction

    order_type: str = "limit"
    count: int = Field(ge=1)
    price_cents: int = Field(ge=1, le=99)

    time_in_force: TimeInForce = TimeInForce.GTC
    post_only: bool = False

    # Status (for existing orders)
    status: Optional[str] = None  # "resting", "canceled", "executed"
    fill_count: int = 0
    remaining_count: Optional[int] = None

    # Fees
    taker_fees_cents: int = 0
    maker_fees_cents: int = 0

    # Timestamps
    created_time: Optional[datetime] = None
    last_update_time: Optional[datetime] = None

    def to_api_payload(self) -> dict:
        """Convert to Kalshi API request format"""
        payload = {
            "ticker": self.ticker,
            "side": self.side.value,
            "action": self.action.value,
            "count": self.count,
            "type": self.order_type,
            f"{self.side.value}_price": self.price_cents,
            "time_in_force": self.time_in_force.value,
        }

        if self.client_order_id:
            payload["client_order_id"] = self.client_order_id

        if self.post_only:
            payload["post_only"] = True

        return payload
