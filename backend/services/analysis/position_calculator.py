"""
Position-aware calculations.

Handles Kalshi's constraint that you cannot hold both YES and NO
on the same market simultaneously.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .fee_calculator import calculate_fee, FeeResult


@dataclass
class Position:
    """User's position in a market."""
    ticker: str
    side: str  # "yes" or "no"
    quantity: int
    avg_price_cents: int
    total_cost_cents: int
    realized_pnl_cents: int = 0

    @property
    def position(self) -> int:
        """Return signed position (positive for yes, negative for no)."""
        return self.quantity if self.side == "yes" else -self.quantity


@dataclass
class OrderbookLevel:
    """Single level in an orderbook."""
    price: int  # cents
    quantity: int


@dataclass
class Orderbook:
    """Orderbook for a market."""
    ticker: str
    yes_bids: List[OrderbookLevel] = field(default_factory=list)
    yes_asks: List[OrderbookLevel] = field(default_factory=list)
    timestamp: Optional[datetime] = None

    def best_yes_bid(self) -> Optional[int]:
        """Best YES bid price."""
        if not self.yes_bids:
            return None
        return max(b.price for b in self.yes_bids)

    def best_yes_ask(self) -> Optional[int]:
        """Best YES ask price."""
        if not self.yes_asks:
            return None
        return min(a.price for a in self.yes_asks)

    def best_no_bid(self) -> Optional[int]:
        """Best NO bid price (complement of YES ask)."""
        yes_ask = self.best_yes_ask()
        return 100 - yes_ask if yes_ask else None

    def best_no_ask(self) -> Optional[int]:
        """Best NO ask price (complement of YES bid)."""
        yes_bid = self.best_yes_bid()
        return 100 - yes_bid if yes_bid else None

    def yes_ask(self) -> Optional[int]:
        """Alias for best_yes_ask."""
        return self.best_yes_ask()

    def take_yes_cost(self, quantity: int) -> Dict[str, Any]:
        """
        Calculate cost to buy YES contracts.

        Returns:
            {
                'total_cost_cents': int,
                'avg_price_cents': float,
                'fillable': int,
                'levels_used': List[dict]
            }
        """
        if not self.yes_asks:
            return {'total_cost_cents': 0, 'avg_price_cents': 0, 'fillable': 0, 'levels_used': []}

        sorted_asks = sorted(self.yes_asks, key=lambda x: x.price)
        total_cost = 0
        filled = 0
        levels_used = []

        for level in sorted_asks:
            if filled >= quantity:
                break
            take = min(level.quantity, quantity - filled)
            total_cost += take * level.price
            filled += take
            levels_used.append({'price': level.price, 'quantity': take})

        avg_price = total_cost / filled if filled > 0 else 0

        return {
            'total_cost_cents': total_cost,
            'avg_price_cents': avg_price,
            'fillable': filled,
            'levels_used': levels_used
        }

    def take_no_cost(self, quantity: int) -> Dict[str, Any]:
        """
        Calculate cost to buy NO contracts.
        NO is the complement of YES, so buying NO at X = selling YES at (100-X).

        Returns same structure as take_yes_cost.
        """
        if not self.yes_bids:
            return {'total_cost_cents': 0, 'avg_price_cents': 0, 'fillable': 0, 'levels_used': []}

        # Sort bids descending (best bid first)
        sorted_bids = sorted(self.yes_bids, key=lambda x: x.price, reverse=True)
        total_cost = 0
        filled = 0
        levels_used = []

        for level in sorted_bids:
            if filled >= quantity:
                break
            no_price = 100 - level.price
            take = min(level.quantity, quantity - filled)
            total_cost += take * no_price
            filled += take
            levels_used.append({'price': no_price, 'quantity': take})

        avg_price = total_cost / filled if filled > 0 else 0

        return {
            'total_cost_cents': total_cost,
            'avg_price_cents': avg_price,
            'fillable': filled,
            'levels_used': levels_used
        }


@dataclass
class OrderEffect:
    """Effect of placing an order given current position"""
    # What we want to do
    desired_ticker: str
    desired_side: str  # "yes" or "no"
    desired_action: str  # "buy" or "sell"
    desired_quantity: int

    # What will actually happen
    will_close_existing: bool
    existing_side: Optional[str]
    existing_quantity: int

    # Cost breakdown
    close_revenue_cents: int  # Revenue from closing existing position
    close_pnl_cents: int  # P&L realized from closing
    new_position_cost_cents: int  # Cost of new position
    net_cost_cents: int  # Total net cost

    # Fees
    close_fee_cents: float
    new_position_fee_cents: float
    total_fee_cents: float

    # Warnings
    warnings: List[str] = field(default_factory=list)


class PositionCalculator:
    """
    Calculate order effects accounting for position constraints.

    Kalshi Rule: Cannot hold both YES and NO simultaneously.
    - Buying YES when holding NO: First sells all NO, then buys YES
    - Buying NO when holding YES: First sells all YES, then buys NO

    This changes the effective cost of trades significantly.
    """

    def calculate_order_effect(
        self,
        ticker: str,
        side: str,
        action: str,
        quantity: int,
        orderbook: Orderbook,
        current_position: Optional[Position] = None,
    ) -> OrderEffect:
        """
        Calculate the full effect of placing an order.

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            action: "buy" or "sell"
            quantity: Number of contracts
            orderbook: Current orderbook
            current_position: User's current position in this market

        Returns:
            OrderEffect with full breakdown of what will happen
        """
        warnings = []

        # Default values
        will_close = False
        existing_side = None
        existing_qty = 0
        close_revenue = 0
        close_pnl = 0
        close_fee = 0.0

        # Check current position
        if current_position and current_position.quantity != 0:
            existing_side = current_position.side
            existing_qty = current_position.quantity

            # Check if we're going opposite to existing position
            if action == "buy" and existing_side != side:
                # Buying opposite side - will close existing first
                will_close = True

                # Calculate revenue from closing
                if existing_side == "yes":
                    # Selling YES - take YES bids
                    best_bid = orderbook.best_yes_bid()
                    if best_bid:
                        close_revenue = existing_qty * best_bid
                        fee_result = calculate_fee(existing_qty, best_bid)
                        close_fee = fee_result.fee_cents
                else:
                    # Selling NO - take NO bids
                    best_bid = orderbook.best_no_bid()
                    if best_bid:
                        close_revenue = existing_qty * best_bid
                        fee_result = calculate_fee(existing_qty, best_bid)
                        close_fee = fee_result.fee_cents

                # Calculate P&L
                close_pnl = close_revenue - current_position.total_cost_cents

                warnings.append(
                    f"Will close {existing_qty} {existing_side.upper()} position first "
                    f"(P&L: {close_pnl/100:+.2f})"
                )

        # Calculate cost of new position
        new_cost = 0
        new_fee = 0.0

        if action == "buy":
            if side == "yes":
                result = orderbook.take_yes_cost(quantity)
                new_cost = result['total_cost_cents']
                if result['fillable'] > 0:
                    avg_price = result['avg_price_cents']
                    fee_result = calculate_fee(result['fillable'], int(avg_price))
                    new_fee = fee_result.fee_cents
            else:
                result = orderbook.take_no_cost(quantity)
                new_cost = result['total_cost_cents']
                if result['fillable'] > 0:
                    avg_price = result['avg_price_cents']
                    fee_result = calculate_fee(result['fillable'], int(avg_price))
                    new_fee = fee_result.fee_cents
        else:  # sell
            # Selling reduces position, revenue instead of cost
            if side == "yes":
                best_bid = orderbook.best_yes_bid()
                if best_bid:
                    new_cost = -(quantity * best_bid)  # Negative = revenue
                    fee_result = calculate_fee(quantity, best_bid)
                    new_fee = fee_result.fee_cents
            else:
                best_bid = orderbook.best_no_bid()
                if best_bid:
                    new_cost = -(quantity * best_bid)
                    fee_result = calculate_fee(quantity, best_bid)
                    new_fee = fee_result.fee_cents

        # Net cost
        net_cost = new_cost - close_revenue  # Subtract revenue from close
        total_fee = close_fee + new_fee

        return OrderEffect(
            desired_ticker=ticker,
            desired_side=side,
            desired_action=action,
            desired_quantity=quantity,
            will_close_existing=will_close,
            existing_side=existing_side,
            existing_quantity=existing_qty,
            close_revenue_cents=close_revenue,
            close_pnl_cents=close_pnl,
            new_position_cost_cents=new_cost,
            net_cost_cents=net_cost,
            close_fee_cents=close_fee,
            new_position_fee_cents=new_fee,
            total_fee_cents=total_fee,
            warnings=warnings,
        )

    def calculate_arbitrage_with_positions(
        self,
        legs: List[dict],  # {'ticker': str, 'side': str, 'quantity': int, 'price_cents': int}
        orderbooks: Dict[str, Orderbook],
        positions: Dict[str, Position],  # ticker -> Position
    ) -> Tuple[int, float, List[str]]:
        """
        Calculate true cost of arbitrage accounting for existing positions.

        Returns:
            (total_net_cost_cents, total_fees_cents, warnings)
        """
        total_cost = 0
        total_fees = 0.0
        warnings = []

        for leg in legs:
            ticker = leg['ticker']
            orderbook = orderbooks.get(ticker)
            position = positions.get(ticker)

            if not orderbook:
                warnings.append(f"No orderbook for {ticker}")
                continue

            effect = self.calculate_order_effect(
                ticker=ticker,
                side=leg['side'],
                action='buy',
                quantity=leg['quantity'],
                orderbook=orderbook,
                current_position=position,
            )

            total_cost += effect.net_cost_cents
            total_fees += effect.total_fee_cents
            warnings.extend(effect.warnings)

        return total_cost, total_fees, warnings


# Singleton
_position_calculator = PositionCalculator()

def calculate_order_effect(
    ticker: str, side: str, action: str, quantity: int,
    orderbook: Orderbook, current_position: Optional[Position] = None
) -> OrderEffect:
    """Convenience function"""
    return _position_calculator.calculate_order_effect(
        ticker, side, action, quantity, orderbook, current_position
    )
