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
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
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
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')

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
            'event_dates': []
        }

        try:
            logger.info("📊 Starting market scan...")

            # Fetch markets in parallel for speed
            range_markets, threshold_markets = await asyncio.gather(
                self._fetch_range_markets(),
                self._fetch_threshold_markets()
            )

            logger.info(f"📊 Fetched {len(range_markets)} range markets, {len(threshold_markets)} threshold markets")

            # ONE-TIME DIAGNOSTIC: Dump first market from each series on first scan
            if self._scan_count == 0:
                import json
                logger.info("=" * 60)
                logger.info("RAW MARKET DATA DUMP (first scan only)")
                logger.info("=" * 60)

                if range_markets:
                    logger.info(f"SAMPLE RANGE MARKET (1 of {len(range_markets)}):")
                    logger.info(json.dumps(range_markets[0], indent=2, default=str))

                if threshold_markets:
                    logger.info(f"SAMPLE THRESHOLD MARKET (1 of {len(threshold_markets)}):")
                    logger.info(json.dumps(threshold_markets[0], indent=2, default=str))

                logger.info("=" * 60)

            # Debug: Log sample tickers to see actual format
            if range_markets:
                sample_range = range_markets[0].get('ticker', 'NO TICKER')
                logger.info(f"📋 Sample range ticker: {sample_range}")
            if threshold_markets:
                sample_thresh = threshold_markets[0].get('ticker', 'NO TICKER')
                logger.info(f"📋 Sample threshold ticker: {sample_thresh}")

            if not range_markets or not threshold_markets:
                logger.warning("⚠️ No markets found - check API connection")
                self._store_scan_result(opportunities, range_markets_simplified, threshold_markets_simplified, calculations, stats)
                return []

            # Simplify markets for UI
            range_markets_simplified = self._simplify_markets(range_markets, 'range')
            threshold_markets_simplified = self._simplify_markets(threshold_markets, 'threshold')
            stats['thresholds_found'] = len(threshold_markets)

            # Group by event date
            range_by_event = self._group_by_event(range_markets)
            thresh_by_event = self._group_by_event(threshold_markets)

            # Find common events (same settlement time)
            common_events = set(range_by_event.keys()) & set(thresh_by_event.keys())
            stats['event_dates'] = sorted(list(common_events))

            logger.info(f"📊 Found {len(common_events)} matching event dates: {', '.join(sorted(common_events))}")

            for event_date in common_events:
                event_ranges = range_by_event[event_date]
                event_thresholds = thresh_by_event[event_date]

                logger.debug(f"🔍 Event {event_date}: {len(event_ranges)} ranges, {len(event_thresholds)} thresholds")

                # Build threshold lookup by strike price
                thresh_lookup = self._build_threshold_lookup(event_thresholds)

                # Debug: Log range coverage vs threshold coverage
                range_floors = sorted([r.get('floor_strike') for r in event_ranges if r.get('floor_strike')])
                range_caps = sorted([r.get('cap_strike') for r in event_ranges if r.get('cap_strike')])
                thresh_strikes = sorted([t.get('floor_strike') for t in event_thresholds if t.get('floor_strike')])

                if range_floors and thresh_strikes:
                    logger.info(f"📋 Event {event_date} coverage:")
                    logger.info(f"   Range floors: {range_floors[:3]}...{range_floors[-3:] if len(range_floors) > 3 else ''}")
                    logger.info(f"   Range caps:   {range_caps[:3]}...{range_caps[-3:] if len(range_caps) > 3 else ''}")
                    logger.info(f"   Thresholds:   {thresh_strikes[:3]}...{thresh_strikes[-3:] if len(thresh_strikes) > 3 else ''}")

                # Check each range for arbitrage
                for range_mkt in event_ranges:
                    stats['ranges_checked'] += 1
                    calc_result = self._calculate_arbitrage(range_mkt, thresh_lookup, event_date, min_edge_percent)
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
                        opp = self._build_opportunity(range_mkt, thresh_lookup, event_date, calc_result)
                        if opp:
                            opportunities.append(opp)
                            logger.info(f"✅ OPPORTUNITY: {opp.range_description} | Cost: {opp.total_cost_cents}¢ | Edge: {opp.edge_percent:.1f}%")

                    elif calc_result.reason == 'missing_prices':
                        stats['missing_prices'] += 1
                    elif calc_result.reason == 'missing_threshold':
                        stats['missing_thresholds'] += 1

            # Sort by edge percent (best first)
            opportunities.sort(key=lambda x: x.edge_percent, reverse=True)

            # Log summary
            if opportunities:
                logger.info(f"✅ Found {len(opportunities)} opportunities! Best: {opportunities[0].edge_percent:.1f}% edge")
            elif stats['near_misses'] > 0:
                logger.info(f"🔥 No arb found, but {stats['near_misses']} near-misses (cost 100-105¢)")
            else:
                best = stats.get('best_cost')
                logger.info(f"📊 No arb found. Best cost: {best}¢" if best else "📊 No valid calculations")

        except Exception as e:
            logger.error(f"❌ Scan error: {e}")
            import traceback
            logger.debug(traceback.format_exc())

        finally:
            self._last_scan_time = time.time()
            self._last_scan_duration_ms = int((time.time() - start_time) * 1000)
            self._scan_count += 1

            # Store complete scan result
            self._store_scan_result(opportunities, range_markets_simplified, threshold_markets_simplified, calculations, stats)

        return opportunities

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
            event_date = self._extract_event_date(ticker) or ''

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
                event_date=event_date
            ))
        return simplified

    def _calculate_arbitrage(
        self,
        range_mkt: Dict,
        thresh_lookup: Dict[float, Dict],
        event_date: str,
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
            event_date=event_date
        )

        if floor is None or cap is None:
            result.reason = 'parse_error'
            return result

        # For range $98,750 - $99,249.99:
        # Lower threshold: need strike at floor - 0.01 (98749.99 means "BTC >= $98,750")
        # Upper threshold: need strike at cap (99249.99 means "BTC >= $99,250")
        lower_thresh_strike = floor - 0.01
        upper_thresh_strike = cap

        # Find threshold markets using fuzzy matching
        lower_thresh = self._find_threshold(lower_thresh_strike, thresh_lookup)
        if not lower_thresh:
            # Also try exact floor value
            lower_thresh = self._find_threshold(floor, thresh_lookup)
        if not lower_thresh:
            logger.debug(f"🔍 Range {range_desc}: No lower threshold for strike {lower_thresh_strike} or {floor}")
            result.reason = 'missing_lower_threshold'
            return result

        upper_thresh = self._find_threshold(upper_thresh_strike, thresh_lookup)
        if not upper_thresh:
            # Also try cap + 0.01 (next boundary)
            upper_thresh = self._find_threshold(cap + 0.01, thresh_lookup)
        if not upper_thresh:
            logger.debug(f"🔍 Range {range_desc}: No upper threshold for strike {upper_thresh_strike}")
            result.reason = 'missing_upper_threshold'
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
        event_date: str,
        calc: CalculationResult
    ) -> Optional[ArbOpportunity]:
        """Build an opportunity from a profitable calculation result using floor_strike/cap_strike."""
        # Use floor_strike and cap_strike directly
        floor = range_mkt.get('floor_strike')
        cap = range_mkt.get('cap_strike')

        # Fallback to ticker parsing
        if floor is None or cap is None:
            floor, cap = self._parse_range_ticker(range_mkt.get('ticker', ''))

        if floor is None or cap is None:
            return None

        # Find thresholds using same logic as _calculate_arbitrage
        lower_thresh_strike = floor - 0.01
        upper_thresh_strike = cap

        lower_thresh = self._find_threshold(lower_thresh_strike, thresh_lookup)
        if not lower_thresh:
            lower_thresh = self._find_threshold(floor, thresh_lookup)

        upper_thresh = self._find_threshold(upper_thresh_strike, thresh_lookup)
        if not upper_thresh:
            upper_thresh = self._find_threshold(cap + 0.01, thresh_lookup)

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
            event_date=event_date,
            settlement_time=range_mkt.get('close_time', ''),
            legs=legs,
            total_cost_cents=calc.total_cost_cents,
            range_description=calc.range_description
        )

    async def _fetch_range_markets(self) -> List[Dict]:
        """Fetch all open KXBTC range markets (only -B tickers)."""
        try:
            events = await self.kalshi.get_events(series_ticker="KXBTC", status="open", with_nested_markets=True, limit=100)
            # Extract markets from events
            all_markets = []
            for event in events:
                event_markets = event.get("markets", [])
                all_markets.extend(event_markets)
            # Filter to only -B (range) tickers, exclude -T (threshold) tickers
            markets = [m for m in all_markets if '-B' in m.get('ticker', '')]
            logger.debug(f"🔍 KXBTC: {len(events)} events, {len(all_markets)} total markets, {len(markets)} range (-B) markets")
            return markets
        except Exception as e:
            logger.error(f"❌ Error fetching range markets: {e}")
            return []

    async def _fetch_threshold_markets(self) -> List[Dict]:
        """Fetch all open KXBTCD threshold markets (only -T tickers)."""
        try:
            events = await self.kalshi.get_events(series_ticker="KXBTCD", status="open", with_nested_markets=True, limit=100)
            # Extract markets from events
            all_markets = []
            for event in events:
                event_markets = event.get("markets", [])
                all_markets.extend(event_markets)
            # Filter to only -T (threshold) tickers
            markets = [m for m in all_markets if '-T' in m.get('ticker', '')]
            logger.debug(f"🔍 KXBTCD: {len(events)} events, {len(all_markets)} total markets, {len(markets)} threshold (-T) markets")
            return markets
        except Exception as e:
            logger.error(f"❌ Error fetching threshold markets: {e}")
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
        """Parse range bounds. KXBTC-26JAN0217-B87500 -> (87500.0, 87749.99)

        Actual format is just -B<lower>, upper bound is lower + 249.99 (ranges are $250 wide).
        """
        match = re.search(r'-B(\d+(?:\.\d+)?)$', ticker)
        if match:
            lower = float(match.group(1))
            upper = lower + 249.99  # Ranges are $250 wide
            return lower, upper
        logger.warning(f"⚠️ Range ticker parse failed: '{ticker}' (expected -B<num> pattern)")
        return None, None

    def _parse_threshold_ticker(self, ticker: str) -> Optional[float]:
        """Parse strike from threshold ticker. KXBTCD-26JAN0217-T97249.99 -> 97249.99"""
        match = re.search(r'-T(\d+(?:\.\d+)?)$', ticker)
        if match:
            return float(match.group(1))
        logger.warning(f"⚠️ Threshold ticker parse failed: '{ticker}' (expected -T<num> pattern)")
        return None

    def _build_threshold_lookup(self, thresholds: List[Dict]) -> Dict[float, Dict]:
        """Build lookup of threshold markets by floor_strike.

        Uses floor_strike field directly instead of parsing tickers.
        Stores both exact and rounded keys for fuzzy matching.
        """
        import math
        lookup = {}
        original_strikes = []
        for mkt in thresholds:
            # Use floor_strike field directly (e.g., 99249.99 means "BTC >= $99,250")
            strike = mkt.get('floor_strike')
            if strike is not None:
                original_strikes.append(strike)
                # Store exact strike
                lookup[strike] = mkt
                # Also store rounded version (97749.99 -> 97750)
                rounded = round(strike)
                if rounded not in lookup:
                    lookup[rounded] = mkt
                # Also store ceiling (97749.99 -> 97750)
                ceiling = math.ceil(strike)
                if ceiling not in lookup:
                    lookup[ceiling] = mkt

        # Debug: Log sample threshold floor_strikes
        if original_strikes:
            sample = sorted(original_strikes)[:10]
            logger.info(f"📋 Sample threshold floor_strikes: {sample}")

        return lookup

    def _find_threshold(self, strike: float, lookup: Dict[float, Dict]) -> Optional[Dict]:
        """Find threshold market with fuzzy matching on strike price.

        Handles decimal precision issues:
        - Range at 97750 needs threshold at 97749.99 (meaning "BTC >= $97,750")
        """
        # Try exact match
        if strike in lookup:
            return lookup[strike]
        # Try rounded
        if round(strike) in lookup:
            return lookup[round(strike)]
        # Try strike - 0.01 (for 97750 -> 97749.99)
        if (strike - 0.01) in lookup:
            return lookup[strike - 0.01]
        # Try strike + 0.01
        if (strike + 0.01) in lookup:
            return lookup[strike + 0.01]
        # Try nearby values within $1
        for offset in [-1, 1, -0.5, 0.5, -0.99, 0.99]:
            if (strike + offset) in lookup:
                return lookup[strike + offset]
        return None

    def _check_range_arbitrage(
        self,
        range_mkt: Dict,
        thresh_lookup: Dict[float, Dict],
        event_date: str
    ) -> Optional[ArbOpportunity]:
        """
        Check if a range has an arbitrage opportunity using floor_strike/cap_strike.

        Trade structure:
        - Buy Range YES (pays if BTC in range)
        - Buy Lower Threshold NO (pays if BTC < lower bound)
        - Buy Upper Threshold YES (pays if BTC >= upper bound)

        ONE of these ALWAYS wins = guaranteed $1 payout.
        """
        # Use floor_strike and cap_strike directly
        floor = range_mkt.get('floor_strike')
        cap = range_mkt.get('cap_strike')

        # Fallback to ticker parsing
        if floor is None or cap is None:
            floor, cap = self._parse_range_ticker(range_mkt.get('ticker', ''))

        if floor is None or cap is None:
            return None

        # Find thresholds using same logic as _calculate_arbitrage
        lower_thresh_strike = floor - 0.01
        upper_thresh_strike = cap

        lower_thresh = self._find_threshold(lower_thresh_strike, thresh_lookup)
        if not lower_thresh:
            lower_thresh = self._find_threshold(floor, thresh_lookup)

        upper_thresh = self._find_threshold(upper_thresh_strike, thresh_lookup)
        if not upper_thresh:
            upper_thresh = self._find_threshold(cap + 0.01, thresh_lookup)

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
                lower_bound=floor,
                upper_bound=cap
            ),
            ArbLeg(
                ticker=lower_thresh['ticker'],
                market_type='threshold',
                side='no',
                action='buy',
                price_cents=lower_no_cost,
                strike=lower_thresh.get('floor_strike', floor)
            ),
            ArbLeg(
                ticker=upper_thresh['ticker'],
                market_type='threshold',
                side='yes',
                action='buy',
                price_cents=upper_cost,
                strike=upper_thresh.get('floor_strike', cap)
            )
        ]

        return ArbOpportunity(
            id=str(uuid.uuid4()),
            event_date=event_date,
            settlement_time=range_mkt.get('close_time', ''),
            legs=legs,
            total_cost_cents=total_cost,
            range_description=f"${floor:,.0f} - ${cap:,.2f}"
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
