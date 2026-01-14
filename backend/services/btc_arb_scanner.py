"""
BTC Arbitrage Scanner
Finds guaranteed-profit arbitrage between BTC range (-B) and threshold (-T) markets.

FIXED: Now fetches from BOTH KXBTC and KXBTCD series, groups by settlement time instead of ticker pattern.
"""

import re
import uuid
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import time

from ..utils.logger import btc_arb_logger as logger, btc_arb_activity


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
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
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


@dataclass
class CalculationResult:
    """Result of checking a single range for arbitrage."""
    range_ticker: str
    range_description: str
    lower_bound: float
    upper_bound: float
    range_yes_ask: Optional[int]
    lower_thresh_ticker: Optional[str]
    lower_thresh_no_cost: Optional[int]
    upper_thresh_ticker: Optional[str]
    upper_thresh_yes_ask: Optional[int]
    total_cost_cents: Optional[int]
    edge_cents: Optional[int]
    is_profitable: bool
    reason: str
    event_date: str

    def to_dict(self):
        return {
            'range_ticker': self.range_ticker,
            'range_description': self.range_description,
            'lower_bound': self.lower_bound,
            'upper_bound': self.upper_bound,
            'range_yes_ask': self.range_yes_ask,
            'lower_thresh_ticker': self.lower_thresh_ticker,
            'lower_thresh_no_cost': self.lower_thresh_no_cost,
            'upper_thresh_ticker': self.upper_thresh_ticker,
            'upper_thresh_yes_ask': self.upper_thresh_yes_ask,
            'total_cost_cents': self.total_cost_cents,
            'edge_cents': self.edge_cents,
            'is_profitable': self.is_profitable,
            'reason': self.reason,
            'event_date': self.event_date
        }


@dataclass
class SimplifiedMarket:
    """Simplified market data for UI display."""
    ticker: str
    market_type: str  # 'range' or 'threshold'
    yes_ask: Optional[int]
    yes_bid: Optional[int]
    no_ask: Optional[int]
    no_bid: Optional[int]
    description: str
    event_date: str
    series: str = ""  # Track which series it came from

    def to_dict(self):
        return asdict(self)


@dataclass
class ScanResult:
    """Complete result of a scan cycle."""
    opportunities: List[ArbOpportunity]
    range_markets: List[SimplifiedMarket]
    threshold_markets: List[SimplifiedMarket]
    calculations: List[CalculationResult]
    stats: Dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))

    def to_dict(self):
        return {
            'opportunities': [o.to_dict() for o in self.opportunities],
            'range_markets': [m.to_dict() for m in self.range_markets],
            'threshold_markets': [m.to_dict() for m in self.threshold_markets],
            'calculations': [c.to_dict() for c in self.calculations],
            'stats': self.stats,
            'timestamp': self.timestamp
        }


class BTCArbitrageScanner:
    """Scans for arbitrage opportunities between BTC range and threshold markets."""

    def __init__(self, kalshi_client):
        self.kalshi = kalshi_client
        self._last_scan_time = 0
        self._last_scan_duration_ms = 0
        self._scan_count = 0
        self._last_scan_result: Optional[ScanResult] = None

    async def scan(self, min_edge_percent: float = 3.0) -> List[ArbOpportunity]:
        """Scan for all arbitrage opportunities. Returns list sorted by edge_percent descending."""
        start_time = time.time()
        opportunities = []
        calculations = []
        range_markets_simplified = []
        threshold_markets_simplified = []
        stats = {
            'ranges_checked': 0,
            'thresholds_found': 0,
            'best_cost': None,
            'worst_cost': None,
            'near_misses': 0,
            'missing_prices': 0,
            'missing_thresholds': 0,
            'settlement_times': [],
            'series_stats': {},
            'event_dates': []  # Legacy field for compatibility
        }

        try:
            logger.info("=" * 60)
            logger.info("[SCAN] Starting BTC arbitrage scan (FIXED: all series + settlement matching)")
            logger.info("=" * 60)

            # Fetch from ALL series, separate into ranges and thresholds
            range_markets, threshold_markets, series_stats = await self._fetch_all_btc_markets()

            stats['series_stats'] = series_stats
            stats['thresholds_found'] = len(threshold_markets)

            logger.info(f"[SCAN] Total: {len(range_markets)} ranges, {len(threshold_markets)} thresholds")

            if not range_markets or not threshold_markets:
                logger.warning("[WARN] No markets found - check API connection")
                self._store_scan_result(opportunities, range_markets_simplified, threshold_markets_simplified, calculations, stats)
                return []

            # Simplify markets for UI
            range_markets_simplified = self._simplify_markets(range_markets, 'range')
            threshold_markets_simplified = self._simplify_markets(threshold_markets, 'threshold')

            # Group by SETTLEMENT TIME (not ticker pattern!)
            range_by_settlement = self._group_by_settlement(range_markets)
            thresh_by_settlement = self._group_by_settlement(threshold_markets)

            logger.info(f"[SCAN] Range settlement times: {sorted(range_by_settlement.keys())[:5]}...")
            logger.info(f"[SCAN] Threshold settlement times: {sorted(thresh_by_settlement.keys())[:5]}...")

            # Find common settlement times
            common_settlements = set(range_by_settlement.keys()) & set(thresh_by_settlement.keys())
            stats['settlement_times'] = sorted(list(common_settlements))
            stats['event_dates'] = stats['settlement_times']  # Legacy compatibility

            logger.info(f"[SCAN] Found {len(common_settlements)} common settlement times")

            if not common_settlements:
                logger.warning("[WARN] NO COMMON SETTLEMENT TIMES - ranges and thresholds don't match!")
                logger.warning("   This usually means KXBTC (hourly) and KXBTCD (daily) have different schedules")
                # Log sample times for debugging
                if range_by_settlement:
                    sample_range = list(range_by_settlement.keys())[:3]
                    logger.info(f"   Sample range settlements: {sample_range}")
                if thresh_by_settlement:
                    sample_thresh = list(thresh_by_settlement.keys())[:3]
                    logger.info(f"   Sample threshold settlements: {sample_thresh}")

            for settlement_time in common_settlements:
                event_ranges = range_by_settlement[settlement_time]
                event_thresholds = thresh_by_settlement[settlement_time]

                logger.info(f"[SEARCH] Settlement {settlement_time}: {len(event_ranges)} ranges, {len(event_thresholds)} thresholds")

                # Build threshold lookup by strike price
                thresh_lookup = self._build_threshold_lookup(event_thresholds)

                # Check each range for arbitrage
                for range_mkt in event_ranges:
                    stats['ranges_checked'] += 1
                    calc_result = self._calculate_arbitrage(range_mkt, thresh_lookup, settlement_time, min_edge_percent)
                    calculations.append(calc_result)

                    if calc_result.total_cost_cents is not None:
                        # Track best/worst costs
                        if stats['best_cost'] is None or calc_result.total_cost_cents < stats['best_cost']:
                            stats['best_cost'] = calc_result.total_cost_cents
                        if stats['worst_cost'] is None or calc_result.total_cost_cents > stats['worst_cost']:
                            stats['worst_cost'] = calc_result.total_cost_cents

                        # Track near misses (cost 100-105)
                        if 100 <= calc_result.total_cost_cents <= 105:
                            stats['near_misses'] += 1

                    if calc_result.is_profitable:
                        opp = self._build_opportunity(range_mkt, thresh_lookup, settlement_time, calc_result)
                        if opp:
                            opportunities.append(opp)
                            logger.info(f"[OK] OPPORTUNITY: {opp.range_description} | Cost: {opp.total_cost_cents}¢ | Edge: {opp.edge_percent:.1f}%")

                    elif calc_result.reason == 'missing_prices':
                        stats['missing_prices'] += 1
                    elif 'missing' in calc_result.reason and 'threshold' in calc_result.reason:
                        stats['missing_thresholds'] += 1

            # Sort by edge percent (best first)
            opportunities.sort(key=lambda x: x.edge_percent, reverse=True)

            # Log summary
            logger.info("=" * 60)
            if opportunities:
                logger.info(f"[OK] Found {len(opportunities)} opportunities! Best: {opportunities[0].edge_percent:.1f}% edge")
            elif stats['near_misses'] > 0:
                logger.info(f"[HOT] No arb found, but {stats['near_misses']} near-misses (cost 100-105¢)")
            else:
                best = stats.get('best_cost')
                logger.info(f"[SCAN] No arb found. Best cost: {best}¢" if best else "[SCAN] No valid calculations")
            logger.info(f"[SCAN] Stats: {stats['ranges_checked']} ranges checked, {stats['missing_thresholds']} missing thresholds, {stats['missing_prices']} missing prices")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"[X] Scan error: {e}")
            import traceback
            logger.debug(traceback.format_exc())

        finally:
            self._last_scan_time = time.time()
            self._last_scan_duration_ms = int((time.time() - start_time) * 1000)
            self._scan_count += 1

            # Store complete scan result
            self._store_scan_result(opportunities, range_markets_simplified, threshold_markets_simplified, calculations, stats)

        return opportunities

    async def _fetch_all_btc_markets(self) -> Tuple[List[Dict], List[Dict], Dict]:
        """
        Fetch all BTC range and threshold markets from ALL series.

        Returns:
            (range_markets, threshold_markets, series_stats)
        """
        all_markets = []
        series_stats = {}

        # Fetch from both KXBTC and KXBTCD series
        for series in ["KXBTC", "KXBTCD"]:
            try:
                events = await self.kalshi.get_events(
                    series_ticker=series,
                    status="open",
                    with_nested_markets=True,
                    limit=100
                )

                series_markets = []
                for event in events:
                    for market in event.get("markets", []):
                        market["_series"] = series
                        market["_event_ticker"] = event.get("event_ticker", "")
                        series_markets.append(market)

                all_markets.extend(series_markets)
                series_stats[series] = {
                    'events': len(events),
                    'markets': len(series_markets)
                }
                logger.info(f"[SCAN] {series}: {len(events)} events, {len(series_markets)} markets")

            except Exception as e:
                logger.warning(f"[WARN] Failed to fetch {series}: {e}")
                series_stats[series] = {'events': 0, 'markets': 0, 'error': str(e)}

        # Separate by market type (range = -B, threshold = -T)
        range_markets = [m for m in all_markets if '-B' in m.get('ticker', '')]
        threshold_markets = [m for m in all_markets if '-T' in m.get('ticker', '')]

        # Log distribution by series
        range_by_series = defaultdict(int)
        thresh_by_series = defaultdict(int)
        for m in range_markets:
            range_by_series[m.get('_series', 'unknown')] += 1
        for m in threshold_markets:
            thresh_by_series[m.get('_series', 'unknown')] += 1

        logger.info(f"[SCAN] Ranges by series: {dict(range_by_series)}")
        logger.info(f"[SCAN] Thresholds by series: {dict(thresh_by_series)}")

        return range_markets, threshold_markets, series_stats

    def _group_by_settlement(self, markets: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group markets by exact settlement time using expiration_time field.

        This is the KEY FIX: instead of parsing ticker patterns (which differ between series),
        we use the actual expiration_time from the API which is the same for markets
        that settle at the same moment.
        """
        groups = defaultdict(list)
        for mkt in markets:
            # Use expiration_time as the canonical settlement identifier
            exp_time = mkt.get('expiration_time') or mkt.get('close_time')
            if exp_time:
                # Truncate to minute precision for matching (ignore seconds/ms)
                # "2026-01-02T22:00:00Z" -> "2026-01-02T22:00"
                key = exp_time[:16]
                groups[key].append(mkt)
        return dict(groups)

    def _store_scan_result(self, opportunities, range_markets, threshold_markets, calculations, stats):
        """Store the complete scan result for later retrieval."""
        self._last_scan_result = ScanResult(
            opportunities=opportunities,
            range_markets=range_markets,
            threshold_markets=threshold_markets,
            calculations=calculations,
            stats=stats
        )

    def get_last_scan_result(self) -> Optional[ScanResult]:
        """Get the most recent scan result."""
        return self._last_scan_result

    def _simplify_markets(self, markets: List[Dict], market_type: str) -> List[SimplifiedMarket]:
        """Extract key fields from markets for UI display using floor_strike/cap_strike."""
        simplified = []
        for mkt in markets:
            ticker = mkt.get('ticker', '')
            exp_time = mkt.get('expiration_time') or mkt.get('close_time') or ''
            event_date = exp_time[:16] if exp_time else ''
            series = mkt.get('_series', '')

            if market_type == 'range':
                # Use floor_strike and cap_strike directly
                floor = mkt.get('floor_strike')
                cap = mkt.get('cap_strike')
                if floor is not None and cap is not None:
                    desc = f"${floor:,.0f} - ${cap:,.2f}"
                else:
                    # Fallback to ticker parsing
                    lower, upper = self._parse_range_ticker(ticker)
                    desc = f"${lower:,.0f} - ${upper:,.2f}" if lower and upper else ticker
            else:
                # Use floor_strike for threshold
                strike = mkt.get('floor_strike')
                if strike is not None:
                    desc = f"≥ ${strike:,.0f}"
                else:
                    # Fallback to ticker parsing
                    strike = self._parse_threshold_ticker(ticker)
                    desc = f"≥ ${strike:,.0f}" if strike else ticker

            simplified.append(SimplifiedMarket(
                ticker=ticker,
                market_type=market_type,
                yes_ask=mkt.get('yes_ask'),
                yes_bid=mkt.get('yes_bid'),
                no_ask=100 - mkt.get('yes_bid') if mkt.get('yes_bid') else None,
                no_bid=100 - mkt.get('yes_ask') if mkt.get('yes_ask') else None,
                description=desc,
                event_date=event_date,
                series=series
            ))
        return simplified

    def _calculate_arbitrage(
        self,
        range_mkt: Dict,
        thresh_lookup: Dict[float, Dict],
        settlement_time: str,
        min_edge_percent: float
    ) -> CalculationResult:
        """Calculate arbitrage for a single range using floor_strike/cap_strike fields."""
        ticker = range_mkt.get('ticker', '')

        # Use floor_strike and cap_strike directly instead of parsing ticker
        floor = range_mkt.get('floor_strike')
        cap = range_mkt.get('cap_strike')

        # Fallback to ticker parsing if fields missing
        if floor is None or cap is None:
            floor, cap = self._parse_range_ticker(ticker)

        range_desc = f"${floor:,.0f} - ${cap:,.2f}" if floor and cap else ticker

        # Base result
        result = CalculationResult(
            range_ticker=ticker,
            range_description=range_desc,
            lower_bound=floor or 0,
            upper_bound=cap or 0,
            range_yes_ask=None,
            lower_thresh_ticker=None,
            lower_thresh_no_cost=None,
            upper_thresh_ticker=None,
            upper_thresh_yes_ask=None,
            total_cost_cents=None,
            edge_cents=None,
            is_profitable=False,
            reason='',
            event_date=settlement_time
        )

        if floor is None or cap is None:
            result.reason = 'parse_error'
            return result

        # For range $X to $Y (e.g., $87,500 - $87,749.99):
        # Lower threshold: need "BTC >= $X" (floor_strike = X or X-0.01)
        # Upper threshold: need "BTC >= $Y+0.01" rounded to next boundary
        lower_thresh = self._find_threshold(floor, thresh_lookup)
        if not lower_thresh:
            lower_thresh = self._find_threshold(floor - 0.01, thresh_lookup)

        if not lower_thresh:
            result.reason = f'missing_lower_threshold (need strike ~{floor})'
            return result

        # Upper threshold: cap is like 87749.99, we need threshold at 87750
        upper_thresh = self._find_threshold(cap + 0.01, thresh_lookup)
        if not upper_thresh:
            # Try next $250 boundary
            next_boundary = ((int(cap) // 250) + 1) * 250
            upper_thresh = self._find_threshold(next_boundary, thresh_lookup)
        if not upper_thresh:
            upper_thresh = self._find_threshold(round(cap + 1), thresh_lookup)

        if not upper_thresh:
            result.reason = f'missing_upper_threshold (need strike ~{cap + 0.01})'
            return result

        result.lower_thresh_ticker = lower_thresh.get('ticker')
        result.upper_thresh_ticker = upper_thresh.get('ticker')

        # Get prices (in cents)
        range_yes_ask = range_mkt.get('yes_ask')
        lower_yes_bid = lower_thresh.get('yes_bid')
        upper_yes_ask = upper_thresh.get('yes_ask')

        result.range_yes_ask = range_yes_ask
        result.upper_thresh_yes_ask = upper_yes_ask

        # Calculate lower NO cost (buying NO = selling YES)
        if lower_yes_bid is not None:
            result.lower_thresh_no_cost = 100 - lower_yes_bid

        # Need all prices to calculate
        if not all([range_yes_ask, lower_yes_bid, upper_yes_ask]):
            result.reason = 'missing_prices'
            return result

        # Calculate costs
        range_cost = range_yes_ask  # Buy Range YES at ask
        lower_no_cost = 100 - lower_yes_bid  # Buy Lower Threshold NO (100 - YES bid)
        upper_cost = upper_yes_ask  # Buy Upper Threshold YES at ask

        total_cost = range_cost + lower_no_cost + upper_cost
        edge_cents = 100 - total_cost

        result.total_cost_cents = total_cost
        result.edge_cents = edge_cents

        # Check profitability
        if total_cost >= 100:
            edge_percent = (edge_cents / total_cost) * 100 if total_cost > 0 else 0
            if total_cost <= 105:
                result.reason = f'near_miss (cost {total_cost}¢, need <100¢)'
            else:
                result.reason = f'too_expensive (cost {total_cost}¢ > 100¢)'
            return result

        # We have arbitrage!
        edge_percent = (edge_cents / total_cost) * 100
        if edge_percent < min_edge_percent:
            result.reason = f'below_threshold ({edge_percent:.1f}% < {min_edge_percent}%)'
            return result

        result.is_profitable = True
        result.reason = f'profitable ({edge_percent:.1f}% edge)'
        return result

    def _build_opportunity(
        self,
        range_mkt: Dict,
        thresh_lookup: Dict[float, Dict],
        settlement_time: str,
        calc: CalculationResult
    ) -> Optional[ArbOpportunity]:
        """Build an opportunity from a profitable calculation result."""
        floor = range_mkt.get('floor_strike')
        cap = range_mkt.get('cap_strike')

        if floor is None or cap is None:
            floor, cap = self._parse_range_ticker(range_mkt.get('ticker', ''))

        if floor is None or cap is None:
            return None

        # Find thresholds using same logic as _calculate_arbitrage
        lower_thresh = self._find_threshold(floor, thresh_lookup)
        if not lower_thresh:
            lower_thresh = self._find_threshold(floor - 0.01, thresh_lookup)

        upper_thresh = self._find_threshold(cap + 0.01, thresh_lookup)
        if not upper_thresh:
            next_boundary = ((int(cap) // 250) + 1) * 250
            upper_thresh = self._find_threshold(next_boundary, thresh_lookup)
        if not upper_thresh:
            upper_thresh = self._find_threshold(round(cap + 1), thresh_lookup)

        if not lower_thresh or not upper_thresh:
            return None

        legs = [
            ArbLeg(
                ticker=range_mkt['ticker'],
                market_type='range',
                side='yes',
                action='buy',
                price_cents=calc.range_yes_ask,
                lower_bound=floor,
                upper_bound=cap
            ),
            ArbLeg(
                ticker=lower_thresh['ticker'],
                market_type='threshold',
                side='no',
                action='buy',
                price_cents=calc.lower_thresh_no_cost,
                strike=lower_thresh.get('floor_strike', floor)
            ),
            ArbLeg(
                ticker=upper_thresh['ticker'],
                market_type='threshold',
                side='yes',
                action='buy',
                price_cents=calc.upper_thresh_yes_ask,
                strike=upper_thresh.get('floor_strike', cap)
            )
        ]

        return ArbOpportunity(
            id=str(uuid.uuid4()),
            event_date=settlement_time,
            settlement_time=range_mkt.get('expiration_time') or range_mkt.get('close_time', ''),
            legs=legs,
            total_cost_cents=calc.total_cost_cents,
            range_description=calc.range_description
        )

    def _build_threshold_lookup(self, thresholds: List[Dict]) -> Dict[float, Dict]:
        """
        Build lookup of threshold markets by floor_strike.

        Stores multiple keys for each threshold to enable fuzzy matching:
        - Exact strike (97749.99)
        - Rounded (97750)
        - Ceiling (97750)
        - Integer (97749)
        """
        import math
        lookup = {}

        for mkt in thresholds:
            strike = mkt.get('floor_strike')
            if strike is not None:
                # Store with multiple keys for fuzzy matching
                lookup[strike] = mkt
                lookup[round(strike)] = mkt
                lookup[math.ceil(strike)] = mkt
                lookup[int(strike)] = mkt
                # Also store +/- 0.01 variants
                lookup[strike + 0.01] = mkt
                lookup[strike - 0.01] = mkt

        return lookup

    def _find_threshold(self, strike: float, lookup: Dict[float, Dict]) -> Optional[Dict]:
        """Find threshold market with fuzzy matching on strike price."""
        # Try exact match
        if strike in lookup:
            return lookup[strike]
        # Try rounded
        if round(strike) in lookup:
            return lookup[round(strike)]
        # Try nearby values
        for offset in [0.01, -0.01, 1, -1, 0.5, -0.5, 0.99, -0.99]:
            if (strike + offset) in lookup:
                return lookup[strike + offset]
        return None

    def _parse_range_ticker(self, ticker: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse range bounds. KXBTC-26JAN0217-B87500 -> (87500.0, 87749.99)"""
        match = re.search(r'-B(\d+(?:\.\d+)?)$', ticker)
        if match:
            lower = float(match.group(1))
            upper = lower + 249.99  # Ranges are $250 wide
            return lower, upper
        return None, None

    def _parse_threshold_ticker(self, ticker: str) -> Optional[float]:
        """Parse strike from threshold ticker. KXBTCD-26JAN0217-T97249.99 -> 97249.99"""
        match = re.search(r'-T(\d+(?:\.\d+)?)$', ticker)
        if match:
            return float(match.group(1))
        return None

    def calculate_trade(self, opportunity: ArbOpportunity, budget_cents: int) -> Dict:
        """Calculate trade details for a given budget."""
        cost_per_set = opportunity.total_cost_cents

        if cost_per_set <= 0:
            return {'error': 'Invalid opportunity cost'}

        contracts = budget_cents // cost_per_set

        if contracts <= 0:
            return {'error': 'Budget too small for one contract set'}

        total_cost = contracts * cost_per_set

        # Estimate fees (Kalshi formula)
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

    async def scan_once(self) -> Dict:
        """
        Wrapper for scan() that returns a dict suitable for scanner_db.
        This is called by scanner_service.py.
        """
        opportunities = await self.scan(min_edge_percent=3.0)
        stats = self.get_stats()
        last_result = self.get_last_scan_result()

        return {
            'opportunities': [opp.to_dict() for opp in opportunities],
            'count': len(opportunities),
            'scan_count': stats['total_scans'],
            'last_scan_duration_ms': stats['last_scan_duration_ms'],
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'stats': last_result.stats if last_result else {}
        }

    def get_stats(self) -> Dict:
        """Get scanner statistics."""
        return {
            'last_scan_time': self._last_scan_time,
            'last_scan_duration_ms': self._last_scan_duration_ms,
            'total_scans': self._scan_count
        }
