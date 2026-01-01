"""
BTC Arbitrage Scanner
Finds guaranteed-profit arbitrage between KXBTC (range) and KXBTCD (threshold) markets.
"""

import re
import uuid
import asyncio
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import time


@dataclass
class ArbLeg:
    """Single leg of an arbitrage trade."""
    ticker: str
    market_type: str  # 'range' or 'threshold'
    side: str  # 'yes' or 'no'
    action: str  # 'buy'
    price_cents: int
    strike: Optional[float] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ArbOpportunity:
    """A complete arbitrage opportunity."""
    id: str
    event_date: str
    settlement_time: str
    legs: List[ArbLeg]
    total_cost_cents: int
    guaranteed_payout_cents: int = 100
    edge_cents: int = 0
    edge_percent: float = 0.0
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    range_description: str = ""

    def __post_init__(self):
        self.edge_cents = self.guaranteed_payout_cents - self.total_cost_cents
        if self.total_cost_cents > 0:
            self.edge_percent = (self.edge_cents / self.total_cost_cents) * 100

    def to_dict(self):
        return {
            'id': self.id,
            'event_date': self.event_date,
            'settlement_time': self.settlement_time,
            'legs': [leg.to_dict() for leg in self.legs],
            'total_cost_cents': self.total_cost_cents,
            'guaranteed_payout_cents': self.guaranteed_payout_cents,
            'edge_cents': self.edge_cents,
            'edge_percent': round(self.edge_percent, 2),
            'detected_at': self.detected_at,
            'range_description': self.range_description
        }


class BTCArbitrageScanner:
    """Scans for arbitrage opportunities between BTC range and threshold markets."""

    def __init__(self, kalshi_client):
        self.kalshi = kalshi_client
        self._last_scan_time = 0
        self._last_scan_duration_ms = 0
        self._scan_count = 0

    async def scan(self, min_edge_percent: float = 3.0) -> List[ArbOpportunity]:
        """Scan for all arbitrage opportunities. Returns list sorted by edge_percent descending."""
        start_time = time.time()
        opportunities = []

        try:
            # Fetch markets in parallel for speed
            range_markets, threshold_markets = await asyncio.gather(
                self._fetch_range_markets(),
                self._fetch_threshold_markets()
            )

            if not range_markets or not threshold_markets:
                return []

            # Group by event date
            range_by_event = self._group_by_event(range_markets)
            thresh_by_event = self._group_by_event(threshold_markets)

            # Find common events (same settlement time)
            common_events = set(range_by_event.keys()) & set(thresh_by_event.keys())

            for event_date in common_events:
                event_ranges = range_by_event[event_date]
                event_thresholds = thresh_by_event[event_date]

                # Build threshold lookup by strike price
                thresh_lookup = self._build_threshold_lookup(event_thresholds)

                # Check each range for arbitrage
                for range_mkt in event_ranges:
                    opp = self._check_range_arbitrage(range_mkt, thresh_lookup, event_date)
                    if opp and opp.edge_percent >= min_edge_percent:
                        opportunities.append(opp)

            # Sort by edge percent (best first)
            opportunities.sort(key=lambda x: x.edge_percent, reverse=True)

        except Exception as e:
            print(f"[BTC ARB SCANNER] Scan error: {e}")

        finally:
            self._last_scan_time = time.time()
            self._last_scan_duration_ms = int((time.time() - start_time) * 1000)
            self._scan_count += 1

        return opportunities

    async def _fetch_range_markets(self) -> List[Dict]:
        """Fetch all open KXBTC range markets."""
        try:
            events = await self.kalshi.get_events(series_ticker="KXBTC", status="open", with_nested_markets=True, limit=100)
            # Extract markets from events
            markets = []
            for event in events:
                event_markets = event.get("markets", [])
                markets.extend(event_markets)
            return markets
        except Exception as e:
            print(f"[BTC ARB SCANNER] Error fetching range markets: {e}")
            return []

    async def _fetch_threshold_markets(self) -> List[Dict]:
        """Fetch all open KXBTCD threshold markets."""
        try:
            events = await self.kalshi.get_events(series_ticker="KXBTCD", status="open", with_nested_markets=True, limit=100)
            # Extract markets from events
            markets = []
            for event in events:
                event_markets = event.get("markets", [])
                markets.extend(event_markets)
            return markets
        except Exception as e:
            print(f"[BTC ARB SCANNER] Error fetching threshold markets: {e}")
            return []

    def _group_by_event(self, markets: List[Dict]) -> Dict[str, List[Dict]]:
        """Group markets by event date (e.g., '25DEC3119')."""
        groups = {}
        for mkt in markets:
            ticker = mkt.get('ticker', '')
            event_date = self._extract_event_date(ticker)
            if event_date:
                if event_date not in groups:
                    groups[event_date] = []
                groups[event_date].append(mkt)
        return groups

    def _extract_event_date(self, ticker: str) -> Optional[str]:
        """Extract event date from ticker. KXBTC-25DEC3119-B... -> '25DEC3119'"""
        match = re.search(r'-(\d{2}[A-Z]{3}\d{4})-', ticker)
        return match.group(1) if match else None

    def _parse_range_ticker(self, ticker: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse range bounds. KXBTC-25DEC3119-B87500T87749.99 -> (87500.0, 87749.99)"""
        match = re.search(r'-B(\d+(?:\.\d+)?)T(\d+(?:\.\d+)?)', ticker)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None, None

    def _parse_threshold_ticker(self, ticker: str) -> Optional[float]:
        """Parse strike from threshold ticker. KXBTCD-25DEC3119-T87500 -> 87500.0"""
        match = re.search(r'-T(\d+(?:\.\d+)?)', ticker)
        return float(match.group(1)) if match else None

    def _build_threshold_lookup(self, thresholds: List[Dict]) -> Dict[float, Dict]:
        """Build lookup of threshold markets by strike price."""
        lookup = {}
        for mkt in thresholds:
            strike = self._parse_threshold_ticker(mkt.get('ticker', ''))
            if strike is not None:
                lookup[strike] = mkt
        return lookup

    def _check_range_arbitrage(
        self,
        range_mkt: Dict,
        thresh_lookup: Dict[float, Dict],
        event_date: str
    ) -> Optional[ArbOpportunity]:
        """
        Check if a range has an arbitrage opportunity.

        Trade structure:
        - Buy Range YES (pays if BTC in range)
        - Buy Lower Threshold NO (pays if BTC < lower bound)
        - Buy Upper Threshold YES (pays if BTC >= upper bound)

        ONE of these ALWAYS wins = guaranteed $1 payout.
        """
        # Parse range bounds
        lower, upper = self._parse_range_ticker(range_mkt.get('ticker', ''))
        if lower is None or upper is None:
            return None

        # Find the upper threshold (next boundary above the range)
        upper_thresh_strike = self._find_next_threshold_strike(upper, thresh_lookup)
        if upper_thresh_strike is None:
            return None

        # Get the threshold markets
        lower_thresh = thresh_lookup.get(lower)
        upper_thresh = thresh_lookup.get(upper_thresh_strike)

        if not lower_thresh or not upper_thresh:
            return None

        # Get prices (in cents)
        range_yes_ask = range_mkt.get('yes_ask')
        lower_yes_bid = lower_thresh.get('yes_bid')
        upper_yes_ask = upper_thresh.get('yes_ask')

        # Need all prices to calculate
        if not all([range_yes_ask, lower_yes_bid, upper_yes_ask]):
            return None

        # Calculate costs
        range_cost = range_yes_ask  # Buy Range YES at ask
        lower_no_cost = 100 - lower_yes_bid  # Buy Lower Threshold NO (100 - YES bid)
        upper_cost = upper_yes_ask  # Buy Upper Threshold YES at ask

        total_cost = range_cost + lower_no_cost + upper_cost

        # Arbitrage exists if total cost < 100 cents
        if total_cost >= 100:
            return None

        # Build the opportunity
        legs = [
            ArbLeg(
                ticker=range_mkt['ticker'],
                market_type='range',
                side='yes',
                action='buy',
                price_cents=range_cost,
                lower_bound=lower,
                upper_bound=upper
            ),
            ArbLeg(
                ticker=lower_thresh['ticker'],
                market_type='threshold',
                side='no',
                action='buy',
                price_cents=lower_no_cost,
                strike=lower
            ),
            ArbLeg(
                ticker=upper_thresh['ticker'],
                market_type='threshold',
                side='yes',
                action='buy',
                price_cents=upper_cost,
                strike=upper_thresh_strike
            )
        ]

        return ArbOpportunity(
            id=str(uuid.uuid4()),
            event_date=event_date,
            settlement_time=range_mkt.get('close_time', ''),
            legs=legs,
            total_cost_cents=total_cost,
            range_description=f"${lower:,.0f} - ${upper:,.2f}"
        )

    def _find_next_threshold_strike(
        self,
        upper_bound: float,
        thresh_lookup: Dict[float, Dict]
    ) -> Optional[float]:
        """
        Find the threshold strike that matches the range's upper bound.
        Range $87,500-$87,749.99 needs threshold at $87,750.
        """
        # Try exact next strike (upper + 0.01 rounded)
        next_strike = round(upper_bound + 0.01, 0)
        if next_strike in thresh_lookup:
            return next_strike

        # Try common increments (250, 500, 1000)
        for increment in [250, 500, 1000]:
            candidate = (int(upper_bound / increment) + 1) * increment
            if candidate in thresh_lookup:
                return candidate

        # Find closest strike above upper bound
        available = sorted([s for s in thresh_lookup.keys() if s > upper_bound])
        return available[0] if available else None

    def calculate_trade(self, opportunity: ArbOpportunity, budget_cents: int) -> Dict:
        """Calculate trade details for a given budget."""
        cost_per_set = opportunity.total_cost_cents

        if cost_per_set <= 0:
            return {'error': 'Invalid opportunity cost'}

        # Calculate max contracts from budget
        contracts = budget_cents // cost_per_set

        if contracts <= 0:
            return {'error': 'Budget too small for one contract set'}

        total_cost = contracts * cost_per_set

        # Estimate fees (Kalshi formula: ceil(0.07 * contracts * price * (1-price)))
        total_fees = 0
        for leg in opportunity.legs:
            price = leg.price_cents / 100
            leg_fee = max(1, int(0.07 * contracts * price * (1 - price) * 100 + 0.99))
            total_fees += leg_fee

        guaranteed_payout = contracts * 100
        guaranteed_profit = guaranteed_payout - total_cost - total_fees

        return {
            'opportunity_id': opportunity.id,
            'contracts_per_leg': contracts,
            'total_cost_cents': total_cost,
            'total_fees_cents': total_fees,
            'guaranteed_payout_cents': guaranteed_payout,
            'guaranteed_profit_cents': guaranteed_profit,
            'return_percent': round((guaranteed_profit / (total_cost + total_fees)) * 100, 2) if (total_cost + total_fees) > 0 else 0
        }

    def get_stats(self) -> Dict:
        """Get scanner statistics."""
        return {
            'last_scan_time': self._last_scan_time,
            'last_scan_duration_ms': self._last_scan_duration_ms,
            'total_scans': self._scan_count
        }
