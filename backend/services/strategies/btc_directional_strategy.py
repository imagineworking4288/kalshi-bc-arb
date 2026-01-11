"""
BTC Directional Strategy using Logistic Probability Model.

Finds mispriced BTC threshold markets where the model probability
diverges significantly from market price.

Logistic Model:
    P(BTC >= strike) = 1 / (1 + exp(-k * (price - strike) / volatility))

    Where:
    - price: Current BTC spot price
    - strike: Threshold strike price
    - volatility: Expected price movement to settlement
    - k: Steepness parameter (default 2.5)

Key Features:
- Uses SpotPriceClient for real-time BTC price
- Configurable volatility based on time-to-settlement
- Filters by minimum edge and confidence thresholds
"""

import math
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from backend.services.core.base_strategy import (
    BaseStrategy,
    StrategyType,
    SignalType,
    TradingSignal,
    SignalLeg,
)
from backend.services.spot_price_client import SpotPriceClient
from backend.services.log_config import get_logger

from . import register_strategy

logger = get_logger("btc_directional_strategy")


@register_strategy
class BTCDirectionalStrategy(BaseStrategy):
    """
    BTC directional trading strategy using logistic probability model.

    Scans BTC threshold markets (KXBTCD series) for mispriced contracts
    where the model probability diverges from market price.

    Configuration:
        min_edge_percent: Minimum edge to generate signal (default 8.0%)
        base_volatility_percent: Base hourly volatility (default 1.5%)
        min_time_to_settlement_hours: Skip markets settling too soon (default 1.0)
        max_time_to_settlement_hours: Skip markets settling too far out (default 48.0)
        steepness_k: Logistic function steepness (default 2.5)
        scan_interval: Time between scans (default 10 seconds)
    """

    # Class-level strategy_type for registry
    # Note: This shares BTC type with BTCArbitrageStrategy
    # The orchestrator can use metadata to distinguish
    strategy_type = StrategyType.BTC

    def __init__(
        self,
        kalshi_client,
        spot_client: Optional[SpotPriceClient] = None,
        min_edge_percent: float = 8.0,
        base_volatility_percent: float = 1.5,
        min_time_to_settlement_hours: float = 1.0,
        max_time_to_settlement_hours: float = 48.0,
        steepness_k: float = 2.5,
        scan_interval: float = 10.0,
    ):
        """
        Initialize BTCDirectionalStrategy.

        Args:
            kalshi_client: KalshiClient instance for market data
            spot_client: Optional SpotPriceClient (created if not provided)
            min_edge_percent: Minimum model edge to report (default 8.0%)
            base_volatility_percent: Base hourly volatility (default 1.5%)
            min_time_to_settlement_hours: Skip if settling sooner (default 1.0)
            max_time_to_settlement_hours: Skip if settling later (default 48.0)
            steepness_k: Logistic function steepness (default 2.5)
            scan_interval: Seconds between scans (default 10.0)
        """
        super().__init__(StrategyType.BTC, "BTC Directional Strategy")

        self.kalshi_client = kalshi_client
        self.spot_client = spot_client or SpotPriceClient()
        self.min_edge_percent = min_edge_percent
        self.base_volatility_percent = base_volatility_percent
        self.min_time_hours = min_time_to_settlement_hours
        self.max_time_hours = max_time_to_settlement_hours
        self.steepness_k = steepness_k
        self._scan_interval = scan_interval

        # Cache for current spot price
        self._last_spot_price: Optional[float] = None
        self._last_spot_time: Optional[datetime] = None

        logger.info(
            f"BTCDirectionalStrategy initialized: min_edge={min_edge_percent}%, "
            f"volatility={base_volatility_percent}%/hr, scan_interval={scan_interval}s"
        )

    @property
    def scan_interval_seconds(self) -> float:
        """BTC directional scans every 10 seconds by default."""
        return self._scan_interval

    async def scan(self) -> List[TradingSignal]:
        """
        Scan BTC threshold markets for directional opportunities.

        Returns:
            List of TradingSignal objects for mispriced markets
        """
        signals: List[TradingSignal] = []

        try:
            # Get current BTC spot price
            spot = await self.spot_client.get_price("BTC")
            if not spot:
                logger.warning("Failed to get BTC spot price")
                return []

            current_price = spot.price
            self._last_spot_price = current_price
            self._last_spot_time = datetime.now(timezone.utc)

            logger.debug(f"BTC spot price: ${current_price:,.2f}")

            # Fetch threshold markets from KXBTCD series
            markets = await self._fetch_threshold_markets()
            if not markets:
                logger.debug("No threshold markets found")
                return []

            now = datetime.now(timezone.utc)

            for mkt in markets:
                signal = self._evaluate_market(mkt, current_price, now)
                if signal:
                    signals.append(signal)

            if signals:
                # Sort by edge, best first
                signals.sort(key=lambda s: s.edge_percent, reverse=True)
                logger.info(
                    f"BTC directional found {len(signals)} opportunities. "
                    f"Best edge: {signals[0].edge_percent:.1f}%"
                )

        except Exception as e:
            logger.error(f"BTC directional scan error: {e}")

        return signals

    async def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Validate a directional signal before execution.

        Re-checks spot price and market price to ensure edge still exists.
        """
        try:
            # Get fresh spot price
            spot = await self.spot_client.get_price("BTC")
            if not spot:
                logger.warning("Failed to get spot price for validation")
                return False

            current_price = spot.price

            # Get current market data
            market = await self.kalshi_client.get_market(signal.ticker)
            if not market:
                logger.warning(f"Market not found: {signal.ticker}")
                return False

            # Get strike from metadata
            strike = signal.metadata.get("strike")
            if strike is None:
                logger.warning("No strike in signal metadata")
                return False

            # Recalculate model probability
            hours_to_settlement = signal.metadata.get("hours_to_settlement", 24)
            volatility = self._calculate_volatility(hours_to_settlement)
            model_prob = self._logistic_probability(current_price, strike, volatility)

            # Get current market price
            leg = signal.legs[0] if signal.legs else None
            if not leg:
                return False

            if leg.side == "yes":
                current_market_price = market.get("yes_ask")
            else:
                yes_bid = market.get("yes_bid")
                current_market_price = 100 - yes_bid if yes_bid else None

            if current_market_price is None:
                return False

            market_prob = current_market_price / 100.0

            # Recalculate edge
            if leg.side == "yes":
                edge = ((model_prob - market_prob) / market_prob) * 100
            else:
                edge = ((market_prob - model_prob) / (1 - market_prob)) * 100

            # Allow some slippage from original edge
            min_required = self.min_edge_percent * 0.6  # Allow 40% slippage

            if edge < min_required:
                logger.info(
                    f"Edge degraded: {edge:.1f}% < {min_required:.1f}% (was {signal.edge_percent:.1f}%)"
                )
                return False

            logger.info(f"Signal validated: edge={edge:.1f}%, spot=${current_price:,.0f}")
            return True

        except Exception as e:
            logger.error(f"Error validating signal: {e}")
            return False

    async def _fetch_threshold_markets(self) -> List[Dict]:
        """Fetch BTC threshold markets from KXBTCD series."""
        try:
            events = await self.kalshi_client.get_events(
                series_ticker="KXBTCD",
                status="open",
                with_nested_markets=True,
                limit=50,
            )

            markets = []
            for event in events:
                for mkt in event.get("markets", []):
                    # Only threshold markets (have -T in ticker)
                    ticker = mkt.get("ticker", "")
                    if "-T" in ticker:
                        mkt["_event_ticker"] = event.get("event_ticker", "")
                        markets.append(mkt)

            logger.debug(f"Fetched {len(markets)} threshold markets")
            return markets

        except Exception as e:
            logger.error(f"Error fetching threshold markets: {e}")
            return []

    def _evaluate_market(
        self,
        market: Dict,
        spot_price: float,
        now: datetime,
    ) -> Optional[TradingSignal]:
        """
        Evaluate a single threshold market for directional opportunity.

        Args:
            market: Market data from Kalshi
            spot_price: Current BTC spot price
            now: Current timestamp

        Returns:
            TradingSignal if opportunity found, None otherwise
        """
        ticker = market.get("ticker", "")
        strike = market.get("floor_strike")

        if strike is None:
            return None

        # Calculate time to settlement
        exp_time_str = market.get("expiration_time") or market.get("close_time")
        if not exp_time_str:
            return None

        try:
            # Parse expiration time
            exp_time = datetime.fromisoformat(exp_time_str.replace("Z", "+00:00"))
            time_delta = exp_time - now
            hours_to_settlement = time_delta.total_seconds() / 3600
        except (ValueError, TypeError):
            return None

        # Filter by time constraints
        if hours_to_settlement < self.min_time_hours:
            return None  # Too close to settlement
        if hours_to_settlement > self.max_time_hours:
            return None  # Too far out

        # Calculate volatility based on time
        volatility = self._calculate_volatility(hours_to_settlement)

        # Calculate model probability using logistic function
        model_prob = self._logistic_probability(spot_price, strike, volatility)

        # Get market prices
        yes_ask = market.get("yes_ask")
        yes_bid = market.get("yes_bid")

        if yes_ask is None or yes_bid is None:
            return None

        market_prob_yes = yes_ask / 100.0
        market_prob_no = (100 - yes_bid) / 100.0

        # Determine trade direction based on where edge is
        edge_yes = ((model_prob - market_prob_yes) / market_prob_yes) * 100
        edge_no = (((1 - model_prob) - market_prob_no) / market_prob_no) * 100

        # Take the better edge
        if edge_yes > edge_no and edge_yes >= self.min_edge_percent:
            # Buy YES - model says more likely to hit threshold
            side = "yes"
            action = "buy"
            price = yes_ask
            edge = edge_yes
            signal_type = SignalType.BUY_YES
        elif edge_no >= self.min_edge_percent:
            # Buy NO - model says less likely to hit threshold
            side = "no"
            action = "buy"
            price = 100 - yes_bid
            edge = edge_no
            signal_type = SignalType.BUY_NO
        else:
            return None  # No significant edge

        # Calculate confidence based on distance from strike
        distance_percent = abs(spot_price - strike) / spot_price * 100
        confidence = self._calculate_confidence(distance_percent, volatility, hours_to_settlement)

        # Create signal
        signal = TradingSignal.create(
            strategy_type=StrategyType.BTC,
            ticker=ticker,
            signal_type=signal_type,
            edge_percent=edge,
            model_prob=model_prob if side == "yes" else (1 - model_prob),
            market_price=price,
            recommended_size=1,
            confidence=confidence,
            is_arbitrage=False,
            legs=[
                SignalLeg(
                    ticker=ticker,
                    side=side,
                    action=action,
                    price_cents=price,
                    strike=strike,
                    description=f"BTC threshold ${strike:,.0f} {side.upper()}",
                )
            ],
            expires_in_seconds=int(min(300, hours_to_settlement * 60)),  # 5 min or less
            metadata={
                "strike": strike,
                "spot_price": spot_price,
                "hours_to_settlement": hours_to_settlement,
                "volatility_percent": volatility,
                "model_probability": model_prob,
                "distance_percent": distance_percent,
                "strategy_name": "btc_directional",
            },
        )

        logger.debug(
            f"{ticker}: strike=${strike:,.0f}, spot=${spot_price:,.0f}, "
            f"model={model_prob:.2f}, market={price}c, edge={edge:.1f}%"
        )

        return signal

    def _logistic_probability(
        self,
        current_price: float,
        strike: float,
        volatility: float,
    ) -> float:
        """
        Calculate probability that BTC >= strike using logistic function.

        P(BTC >= strike) = 1 / (1 + exp(-k * (price - strike) / volatility_dollars))

        Args:
            current_price: Current BTC spot price
            strike: Threshold strike price
            volatility: Expected volatility in percent

        Returns:
            Probability between 0 and 1
        """
        # Convert percent volatility to dollar terms
        volatility_dollars = current_price * volatility / 100

        if volatility_dollars <= 0:
            # Degenerate case
            return 1.0 if current_price >= strike else 0.0

        # Logistic function
        x = self.steepness_k * (current_price - strike) / volatility_dollars

        # Clamp to avoid overflow
        x = max(-20, min(20, x))

        prob = 1.0 / (1.0 + math.exp(-x))

        return prob

    def _calculate_volatility(self, hours: float) -> float:
        """
        Calculate expected volatility based on time to settlement.

        Uses square root of time scaling (common in finance).

        Args:
            hours: Hours until settlement

        Returns:
            Volatility in percent
        """
        # Base volatility scales with sqrt of time
        # base_volatility is per hour, so for N hours: base * sqrt(N)
        return self.base_volatility_percent * math.sqrt(max(1, hours))

    def _calculate_confidence(
        self,
        distance_percent: float,
        volatility: float,
        hours: float,
    ) -> float:
        """
        Calculate confidence in the signal.

        Higher confidence when:
        - Strike is further from current price (clearer edge)
        - More time to settlement (more price movement)
        - Lower volatility (more predictable)

        Args:
            distance_percent: Distance from strike as percent of price
            volatility: Expected volatility percent
            hours: Hours to settlement

        Returns:
            Confidence between 0.5 and 1.0
        """
        # Base confidence on how many "volatility units" away the strike is
        if volatility > 0:
            vol_units = distance_percent / volatility
        else:
            vol_units = 0

        # More vol units = clearer edge = higher confidence
        # Cap at 2 vol units for max confidence
        confidence = 0.5 + 0.5 * min(vol_units / 2.0, 1.0)

        # Slight boost for more time (more data to work with)
        if hours > 6:
            confidence = min(1.0, confidence * 1.05)

        return round(confidence, 2)

    def get_last_spot_price(self) -> Optional[float]:
        """Get the last cached spot price."""
        return self._last_spot_price

    def get_status(self) -> Dict[str, Any]:
        """Get strategy status including spot price info."""
        base_status = super().get_status()
        base_status.update({
            "last_spot_price": self._last_spot_price,
            "last_spot_time": (
                self._last_spot_time.isoformat() if self._last_spot_time else None
            ),
            "config": {
                "min_edge_percent": self.min_edge_percent,
                "base_volatility_percent": self.base_volatility_percent,
                "steepness_k": self.steepness_k,
                "min_time_hours": self.min_time_hours,
                "max_time_hours": self.max_time_hours,
            },
        })
        return base_status
