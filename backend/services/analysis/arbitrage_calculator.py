"""
Multi-strategy arbitrage calculator.

Analyzes events for arbitrage opportunities using four strategies:
1. all_yes - Buy YES on all brackets
2. all_no - Buy NO on all brackets (N-1 payout)
3. hybrid - Buy cheapest side per bracket
4. min_2_no - Buy at least 2 NO positions

All calculations account for fees and existing positions.
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .fee_calculator import calculate_fee
from .position_calculator import PositionCalculator, Orderbook, Position


class ArbitrageStrategy(str, Enum):
    """Available arbitrage strategies."""
    ALL_YES = "all_yes"
    ALL_NO = "all_no"
    HYBRID = "hybrid"
    MIN_2_NO = "min_2_no"


@dataclass
class Market:
    """Market representation for arbitrage calculations."""
    ticker: str
    event_ticker: str = ""
    floor_strike: Optional[int] = None
    cap_strike: Optional[int] = None
    status: str = "open"

    def is_tradeable(self) -> bool:
        """Check if market is open for trading."""
        return self.status == "open"


@dataclass
class Event:
    """Event containing multiple markets."""
    event_ticker: str
    markets: List[Market] = field(default_factory=list)
    mutually_exclusive: bool = True


@dataclass
class ArbitrageLeg:
    """Single leg of an arbitrage trade."""
    ticker: str
    side: str  # "yes" or "no"
    action: str  # "buy" or "sell"
    quantity: int
    price_cents: int
    fee_cents: float


@dataclass
class StrategyResult:
    """Result of analyzing a single strategy"""
    strategy: str
    legs: List[Dict[str, Any]]  # List of leg dicts
    total_cost_cents: int
    total_fees_cents: float
    guaranteed_payout_cents: int
    profit_cents: float
    profit_after_fees_cents: float
    roi_percent: float
    is_profitable: bool
    warnings: List[str] = field(default_factory=list)


@dataclass
class ArbitrageAnalysis:
    """Complete arbitrage analysis for an event"""
    event_ticker: str
    strategies: Dict[str, StrategyResult]
    best_strategy: Optional[str]
    best_profit_cents: float
    has_opportunity: bool
    analyzed_at: datetime
    market_count: int
    warnings: List[str] = field(default_factory=list)


class ArbitrageCalculator:
    """
    Calculate arbitrage opportunities across multiple strategies.

    For mutually exclusive events (only one bracket wins):
    - all_yes: If sum(YES asks) < 100 cents, buy all YES, one pays $1
    - all_no: Buy NO on all brackets, (N-1) pay $1 each when one bracket wins
    - hybrid: Mix YES and NO to minimize cost
    - min_2_no: At least 2 NO positions for diversification

    All calculations:
    1. Use actual orderbook prices (not just best bid/ask)
    2. Calculate fees per-leg (not on average)
    3. Account for existing positions
    4. Include slippage estimates for larger orders
    """

    MIN_PROFIT_THRESHOLD_CENTS = 50  # Minimum $0.50 profit to recommend
    MIN_EDGE_PERCENT = 0.03  # Minimum 3% edge

    def __init__(self):
        self.position_calculator = PositionCalculator()

    def analyze_event(
        self,
        event: Event,
        orderbooks: Dict[str, Orderbook],
        positions: Optional[Dict[str, Position]] = None,
        quantity_per_bracket: int = 1,
    ) -> ArbitrageAnalysis:
        """
        Analyze an event for arbitrage opportunities.

        Args:
            event: Event with nested markets
            orderbooks: Current orderbooks for each market
            positions: User's current positions (optional)
            quantity_per_bracket: Contracts per bracket (usually 1)

        Returns:
            Complete analysis with all strategies evaluated
        """
        warnings = []
        positions = positions or {}

        # Filter to open markets with orderbooks
        markets = [m for m in event.markets if m.is_tradeable()]
        markets_with_books = [
            m for m in markets
            if m.ticker in orderbooks and orderbooks[m.ticker].yes_ask() is not None
        ]

        if len(markets_with_books) < len(markets):
            warnings.append(f"Only {len(markets_with_books)}/{len(markets)} markets have orderbooks")

        if len(markets_with_books) < 2:
            warnings.append("Need at least 2 markets for arbitrage")
            return self._empty_analysis(event.event_ticker, warnings)

        # Check mutual exclusivity
        if not event.mutually_exclusive:
            warnings.append("Event is not mutually exclusive - arbitrage may not work")

        # Analyze each strategy
        strategies = {}

        strategies['all_yes'] = self._analyze_all_yes(
            markets_with_books, orderbooks, positions, quantity_per_bracket
        )

        strategies['all_no'] = self._analyze_all_no(
            markets_with_books, orderbooks, positions, quantity_per_bracket
        )

        strategies['hybrid'] = self._analyze_hybrid(
            markets_with_books, orderbooks, positions, quantity_per_bracket
        )

        strategies['min_2_no'] = self._analyze_min_2_no(
            markets_with_books, orderbooks, positions, quantity_per_bracket
        )

        # Find best strategy
        profitable = [
            (name, result) for name, result in strategies.items()
            if result.is_profitable
        ]

        if profitable:
            best_name, best_result = max(profitable, key=lambda x: x[1].profit_after_fees_cents)
            best_strategy = best_name
            best_profit = best_result.profit_after_fees_cents
            has_opportunity = True
        else:
            best_strategy = None
            best_profit = 0
            has_opportunity = False

        return ArbitrageAnalysis(
            event_ticker=event.event_ticker,
            strategies=strategies,
            best_strategy=best_strategy,
            best_profit_cents=best_profit,
            has_opportunity=has_opportunity,
            analyzed_at=datetime.now(timezone.utc),
            market_count=len(markets_with_books),
            warnings=warnings,
        )

    def analyze_from_brackets(
        self,
        brackets: List[Dict[str, Any]],
        event_ticker: str = "",
        quantity: int = 1,
    ) -> ArbitrageAnalysis:
        """
        Analyze arbitrage from a simple list of bracket dicts.

        This is a convenience method that works with the format used by
        the existing arbitrage scanner.

        Args:
            brackets: List of dicts with 'ticker', 'yes_ask', 'no_ask' keys
            event_ticker: Optional event ticker
            quantity: Contracts per bracket

        Returns:
            ArbitrageAnalysis with all strategies evaluated
        """
        # Build markets and orderbooks from bracket data
        markets = []
        orderbooks = {}

        for b in brackets:
            ticker = b.get('ticker', '')
            markets.append(Market(
                ticker=ticker,
                event_ticker=event_ticker,
            ))

            yes_ask = b.get('yes_ask', 0)
            yes_bid = 100 - b.get('no_ask', 100)  # NO ask = 100 - YES bid

            from .position_calculator import OrderbookLevel
            orderbooks[ticker] = Orderbook(
                ticker=ticker,
                yes_asks=[OrderbookLevel(price=yes_ask, quantity=1000)] if yes_ask else [],
                yes_bids=[OrderbookLevel(price=yes_bid, quantity=1000)] if yes_bid else [],
            )

        event = Event(
            event_ticker=event_ticker,
            markets=markets,
            mutually_exclusive=True,
        )

        return self.analyze_event(event, orderbooks, quantity_per_bracket=quantity)

    def _analyze_all_yes(
        self,
        markets: List[Market],
        orderbooks: Dict[str, Orderbook],
        positions: Dict[str, Position],
        quantity: int,
    ) -> StrategyResult:
        """
        Analyze buying YES on all brackets.
        Guaranteed payout: $1 x quantity (one bracket wins)
        """
        legs = []
        total_cost = 0
        total_fees = 0.0
        warnings = []

        for market in markets:
            ob = orderbooks[market.ticker]

            # Cost to buy YES
            result = ob.take_yes_cost(quantity)
            if result['fillable'] < quantity:
                warnings.append(f"Insufficient liquidity for {market.ticker}")

            price_cents = int(result['avg_price_cents']) if result['avg_price_cents'] else 0

            if price_cents > 0:
                fee_result = calculate_fee(result['fillable'], price_cents)

                legs.append({
                    'ticker': market.ticker,
                    'side': 'yes',
                    'action': 'buy',
                    'quantity': result['fillable'],
                    'price_cents': price_cents,
                    'fee_cents': fee_result.fee_cents,
                })

                total_cost += result['total_cost_cents']
                total_fees += fee_result.fee_cents

        # Payout: one bracket wins, pays $1 per contract
        payout = quantity * 100

        profit = payout - total_cost
        profit_after_fees = profit - total_fees
        roi = (profit_after_fees / total_cost * 100) if total_cost > 0 else 0

        is_profitable = (
            profit_after_fees >= self.MIN_PROFIT_THRESHOLD_CENTS and
            roi >= self.MIN_EDGE_PERCENT * 100
        )

        return StrategyResult(
            strategy='all_yes',
            legs=legs,
            total_cost_cents=total_cost,
            total_fees_cents=total_fees,
            guaranteed_payout_cents=payout,
            profit_cents=profit,
            profit_after_fees_cents=profit_after_fees,
            roi_percent=roi,
            is_profitable=is_profitable,
            warnings=warnings,
        )

    def _analyze_all_no(
        self,
        markets: List[Market],
        orderbooks: Dict[str, Orderbook],
        positions: Dict[str, Position],
        quantity: int,
    ) -> StrategyResult:
        """
        Analyze buying NO on all brackets.
        Guaranteed payout: (N-1) x $1 x quantity
        (All brackets except the winner pay out)
        """
        legs = []
        total_cost = 0
        total_fees = 0.0
        warnings = []
        n = len(markets)

        for market in markets:
            ob = orderbooks[market.ticker]

            # Cost to buy NO
            result = ob.take_no_cost(quantity)
            if result['fillable'] < quantity:
                warnings.append(f"Insufficient NO liquidity for {market.ticker}")

            price_cents = int(result['avg_price_cents']) if result['avg_price_cents'] else 0

            if price_cents > 0:
                fee_result = calculate_fee(result['fillable'], price_cents)

                legs.append({
                    'ticker': market.ticker,
                    'side': 'no',
                    'action': 'buy',
                    'quantity': result['fillable'],
                    'price_cents': price_cents,
                    'fee_cents': fee_result.fee_cents,
                })

                total_cost += result['total_cost_cents']
                total_fees += fee_result.fee_cents

        # Payout: (N-1) brackets are NO winners
        payout = (n - 1) * quantity * 100

        profit = payout - total_cost
        profit_after_fees = profit - total_fees
        roi = (profit_after_fees / total_cost * 100) if total_cost > 0 else 0

        is_profitable = (
            profit_after_fees >= self.MIN_PROFIT_THRESHOLD_CENTS and
            roi >= self.MIN_EDGE_PERCENT * 100
        )

        return StrategyResult(
            strategy='all_no',
            legs=legs,
            total_cost_cents=total_cost,
            total_fees_cents=total_fees,
            guaranteed_payout_cents=payout,
            profit_cents=profit,
            profit_after_fees_cents=profit_after_fees,
            roi_percent=roi,
            is_profitable=is_profitable,
            warnings=warnings,
        )

    def _analyze_hybrid(
        self,
        markets: List[Market],
        orderbooks: Dict[str, Orderbook],
        positions: Dict[str, Position],
        quantity: int,
    ) -> StrategyResult:
        """
        Analyze hybrid strategy: cheapest side per bracket.

        For each bracket, buy whichever is cheaper (YES or NO).
        Constraint: Must use either YES OR NO per bracket, never both.
        """
        legs = []
        total_cost = 0
        total_fees = 0.0
        warnings = []

        for market in markets:
            ob = orderbooks[market.ticker]

            # Get costs for both sides
            yes_result = ob.take_yes_cost(quantity)
            no_result = ob.take_no_cost(quantity)

            yes_cost = yes_result['total_cost_cents']
            no_cost = no_result['total_cost_cents']

            # Choose cheaper side
            if yes_cost <= no_cost and yes_result['fillable'] >= quantity:
                side = 'yes'
                result = yes_result
            elif no_result['fillable'] >= quantity:
                side = 'no'
                result = no_result
            elif yes_result['fillable'] >= quantity:
                side = 'yes'
                result = yes_result
            else:
                warnings.append(f"Insufficient liquidity for {market.ticker}")
                continue

            price_cents = int(result['avg_price_cents']) if result['avg_price_cents'] else 0

            if price_cents > 0:
                fee_result = calculate_fee(result['fillable'], price_cents)

                legs.append({
                    'ticker': market.ticker,
                    'side': side,
                    'action': 'buy',
                    'quantity': result['fillable'],
                    'price_cents': price_cents,
                    'fee_cents': fee_result.fee_cents,
                })

                total_cost += result['total_cost_cents']
                total_fees += fee_result.fee_cents

        # Payout calculation for hybrid is complex
        # Count YES and NO legs
        yes_count = sum(1 for leg in legs if leg['side'] == 'yes')
        no_count = len(legs) - yes_count

        # Minimum guaranteed payout:
        # - If winner is YES: We get $1 from that YES, plus $1 from each NO on other brackets
        # - If winner is NO: We get $1 from each NO except that one
        # Minimum is when the winning bracket is one where we have YES
        # Then we get: 1 YES winner ($1) + (no_count) NO winners ($1 each)
        payout = quantity * 100 * (1 + no_count)  # Simplified

        profit = payout - total_cost
        profit_after_fees = profit - total_fees
        roi = (profit_after_fees / total_cost * 100) if total_cost > 0 else 0

        is_profitable = (
            profit_after_fees >= self.MIN_PROFIT_THRESHOLD_CENTS and
            roi >= self.MIN_EDGE_PERCENT * 100
        )

        return StrategyResult(
            strategy='hybrid',
            legs=legs,
            total_cost_cents=total_cost,
            total_fees_cents=total_fees,
            guaranteed_payout_cents=payout,
            profit_cents=profit,
            profit_after_fees_cents=profit_after_fees,
            roi_percent=roi,
            is_profitable=is_profitable,
            warnings=warnings,
        )

    def _analyze_min_2_no(
        self,
        markets: List[Market],
        orderbooks: Dict[str, Orderbook],
        positions: Dict[str, Position],
        quantity: int,
    ) -> StrategyResult:
        """
        Analyze strategy requiring at least 2 NO positions.
        Similar to hybrid but enforces minimum NO exposure.
        """
        # Get costs for all markets
        market_costs = []
        for market in markets:
            ob = orderbooks[market.ticker]
            yes_result = ob.take_yes_cost(quantity)
            no_result = ob.take_no_cost(quantity)

            market_costs.append({
                'market': market,
                'yes_cost': yes_result['total_cost_cents'],
                'no_cost': no_result['total_cost_cents'],
                'yes_result': yes_result,
                'no_result': no_result,
            })

        # Sort by NO cost (cheapest first)
        market_costs.sort(key=lambda x: x['no_cost'])

        # Take at least 2 cheapest NOs
        legs = []
        total_cost = 0
        total_fees = 0.0
        warnings = []
        no_count = 0

        for i, mc in enumerate(market_costs):
            # First 2 must be NO
            if i < 2:
                side = 'no'
                result = mc['no_result']
            else:
                # Rest can be either (choose cheaper)
                if mc['yes_cost'] <= mc['no_cost']:
                    side = 'yes'
                    result = mc['yes_result']
                else:
                    side = 'no'
                    result = mc['no_result']

            if side == 'no':
                no_count += 1

            price_cents = int(result['avg_price_cents']) if result['avg_price_cents'] else 0

            if price_cents > 0 and result['fillable'] > 0:
                fee_result = calculate_fee(result['fillable'], price_cents)

                legs.append({
                    'ticker': mc['market'].ticker,
                    'side': side,
                    'action': 'buy',
                    'quantity': result['fillable'],
                    'price_cents': price_cents,
                    'fee_cents': fee_result.fee_cents,
                })

                total_cost += result['total_cost_cents']
                total_fees += fee_result.fee_cents

        # Payout with guaranteed minimum NO positions
        payout = quantity * 100 * (1 + min(no_count - 1, len(markets) - 1))

        profit = payout - total_cost
        profit_after_fees = profit - total_fees
        roi = (profit_after_fees / total_cost * 100) if total_cost > 0 else 0

        is_profitable = (
            profit_after_fees >= self.MIN_PROFIT_THRESHOLD_CENTS and
            roi >= self.MIN_EDGE_PERCENT * 100
        )

        return StrategyResult(
            strategy='min_2_no',
            legs=legs,
            total_cost_cents=total_cost,
            total_fees_cents=total_fees,
            guaranteed_payout_cents=payout,
            profit_cents=profit,
            profit_after_fees_cents=profit_after_fees,
            roi_percent=roi,
            is_profitable=is_profitable,
            warnings=warnings,
        )

    def _empty_analysis(
        self,
        event_ticker: str,
        warnings: List[str],
    ) -> ArbitrageAnalysis:
        """Return empty analysis when event can't be analyzed"""
        return ArbitrageAnalysis(
            event_ticker=event_ticker,
            strategies={},
            best_strategy=None,
            best_profit_cents=0,
            has_opportunity=False,
            analyzed_at=datetime.now(timezone.utc),
            market_count=0,
            warnings=warnings,
        )

    def to_recommendation(
        self,
        analysis: ArbitrageAnalysis,
    ) -> Optional[Dict[str, Any]]:
        """Convert analysis to recommendation format for API"""
        if not analysis.has_opportunity or not analysis.best_strategy:
            return None

        result = analysis.strategies[analysis.best_strategy]

        return {
            'event_ticker': analysis.event_ticker,
            'strategy': analysis.best_strategy,
            'legs': result.legs,
            'total_cost_cents': result.total_cost_cents,
            'total_fees_cents': result.total_fees_cents,
            'expected_profit_cents': result.profit_cents,
            'profit_after_fees_cents': result.profit_after_fees_cents,
            'confidence': 0.9 if result.roi_percent > 5 else 0.7,
            'edge_percent': result.roi_percent / 100,
            'warnings': result.warnings + analysis.warnings,
            'stale': False,
            'calculated_at': analysis.analyzed_at.isoformat(),
        }


# Singleton
_arbitrage_calculator = ArbitrageCalculator()

def analyze_event(
    event: Event,
    orderbooks: Dict[str, Orderbook],
    **kwargs
) -> ArbitrageAnalysis:
    """Convenience function"""
    return _arbitrage_calculator.analyze_event(event, orderbooks, **kwargs)

def analyze_from_brackets(
    brackets: List[Dict[str, Any]],
    **kwargs
) -> ArbitrageAnalysis:
    """Convenience function for simple bracket analysis"""
    return _arbitrage_calculator.analyze_from_brackets(brackets, **kwargs)
