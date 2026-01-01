"""
Edge Detection Engine
Identifies mispriced markets by comparing model probabilities to market prices.
"""

import math
import logging
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    ticker: str
    signal_type: str  # 'buy_yes', 'buy_no'
    edge_percent: float
    model_prob: float
    market_price: int  # cents
    recommended_size: int
    source: str
    notes: str = ""


class EdgeDetector:
    """Detects pricing edges across Kalshi markets."""

    def __init__(self, kalshi_client, db):
        self.kalshi = kalshi_client
        self.db = db
        self.min_edge = 10.0  # Will be loaded from config

    async def load_config(self):
        """Load configuration from database."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT min_edge_percent FROM auto_trader_config WHERE id = 1"
            )
            row = await cursor.fetchone()
            if row:
                self.min_edge = row[0]

    async def scan_btc_markets(self) -> List[TradingSignal]:
        """
        Scan Bitcoin price markets for edges.

        Strategy: Compare current BTC price to strike prices.
        If BTC is at $95,000 and market asks "Will BTC be above $90,000?",
        the YES probability should be very high (>95%).
        """
        signals = []

        # Get current BTC price
        btc_price = await self._get_btc_price()
        if not btc_price:
            logger.warning("Could not fetch BTC price for edge detection")
            return signals

        logger.info(f"Current BTC price: ${btc_price:,.2f}")

        # Get all open BTC markets
        try:
            events = await self.kalshi.get_events(
                series_ticker="KXBTCD",
                status="open",
                with_nested_markets=True,
                limit=20
            )

            # Extract markets from events
            all_markets = []
            for event in events:
                markets = event.get("markets", [])
                for market in markets:
                    all_markets.append(market)

            logger.info(f"Scanning {len(all_markets)} BTC markets for edges")

        except Exception as e:
            logger.error(f"Error fetching BTC markets: {e}")
            return signals

        for market in all_markets:
            signal = self._analyze_btc_market(market, btc_price)
            if signal and signal.edge_percent >= self.min_edge:
                signals.append(signal)

        logger.info(f"Found {len(signals)} signals with edge >= {self.min_edge}%")
        return signals

    def _analyze_btc_market(self, market: dict, current_btc: float) -> Optional[TradingSignal]:
        """
        Analyze a single BTC market for edge.

        Market ticker format: KXBTCD-26JAN0217-T99249.99
        - 26JAN02 = January 2, 2026
        - 17 = 5 PM ET settlement
        - T99249.99 = threshold of $99,249.99
        """
        ticker = market.get('ticker', '')

        # Parse strike price from ticker
        strike = self._parse_btc_strike(ticker)
        if not strike:
            return None

        # Get market prices
        yes_ask = market.get('yes_ask')
        no_ask = market.get('no_ask')

        if yes_ask is None or no_ask is None:
            return None

        # Calculate model probability based on current price vs strike
        model_prob = self._calculate_btc_probability(current_btc, strike, market)

        # Calculate edges
        yes_edge = (model_prob * 100) - yes_ask  # If model says 80%, yes_ask is 60¢, edge = 20%
        no_edge = ((1 - model_prob) * 100) - no_ask

        # Generate signal if edge exists
        if yes_edge >= self.min_edge:
            return TradingSignal(
                ticker=ticker,
                signal_type='buy_yes',
                edge_percent=yes_edge,
                model_prob=model_prob,
                market_price=yes_ask,
                recommended_size=self._calculate_position_size(yes_edge),
                source='btc_price_model',
                notes=f"BTC=${current_btc:,.0f}, Strike=${strike:,.0f}, Model={model_prob:.1%}"
            )
        elif no_edge >= self.min_edge:
            return TradingSignal(
                ticker=ticker,
                signal_type='buy_no',
                edge_percent=no_edge,
                model_prob=1 - model_prob,
                market_price=no_ask,
                recommended_size=self._calculate_position_size(no_edge),
                source='btc_price_model',
                notes=f"BTC=${current_btc:,.0f}, Strike=${strike:,.0f}, Model={model_prob:.1%}"
            )

        return None

    def _parse_btc_strike(self, ticker: str) -> Optional[float]:
        """Extract strike price from ticker like KXBTCD-26JAN0217-T99249.99"""
        try:
            if '-T' in ticker:
                strike_str = ticker.split('-T')[1]
                return float(strike_str)
        except (IndexError, ValueError):
            pass
        return None

    def _calculate_btc_probability(self, current: float, strike: float, market: dict) -> float:
        """
        Calculate probability that BTC will be above strike at settlement.

        Simple model based on distance from strike:
        - If current >> strike: high probability (approaching 1.0)
        - If current << strike: low probability (approaching 0.0)
        - If current ≈ strike: ~50%

        Uses logistic function for smooth probability curve.
        """
        # Distance as percentage of strike
        distance_pct = (current - strike) / strike * 100

        # Convert to probability using logistic function
        # Calibrated so ±5% distance ≈ 73%/27% probability
        k = 0.3  # Steepness parameter
        prob = 1 / (1 + math.exp(-k * distance_pct))

        # Clamp to reasonable bounds (avoid 0% or 100% predictions)
        return max(0.02, min(0.98, prob))

    def _calculate_position_size(self, edge_percent: float) -> int:
        """
        Calculate recommended position size based on edge.
        Simplified Kelly Criterion: size proportional to edge.
        """
        # Base size + edge bonus, capped at max
        base = 10
        edge_bonus = int(edge_percent / 5) * 5
        return min(base + edge_bonus, 100)

    async def _get_btc_price(self) -> Optional[float]:
        """Fetch current BTC price from CoinGecko."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "bitcoin", "vs_currencies": "usd"},
                    timeout=10
                )
                data = resp.json()
                return data.get('bitcoin', {}).get('usd')
        except Exception as e:
            logger.error(f"Error fetching BTC price: {e}")
            return None

    async def save_signal(self, signal: TradingSignal) -> int:
        """Save signal to database."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                INSERT INTO trading_signals
                (ticker, signal_type, edge_percent, model_prob, market_price,
                 recommended_size, source, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.ticker, signal.signal_type, signal.edge_percent,
                signal.model_prob, signal.market_price, signal.recommended_size,
                signal.source, signal.notes
            ))
            await conn.commit()
            return cursor.lastrowid

    async def get_pending_signals(self) -> List[dict]:
        """Get all pending signals."""
        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM trading_signals
                WHERE status = 'pending'
                ORDER BY edge_percent DESC
            """)
            rows = await cursor.fetchall()
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
