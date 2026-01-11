"""
BTC Range vs Threshold Arbitrage Strategy.

Wraps BTCArbitrageScanner to find guaranteed-profit arbitrage between
BTC range markets (-B) and threshold markets (-T).

Arbitrage Pattern:
    BTC price lands in range $X to $Y (e.g., $87,500 - $87,749.99)

    Buy: Range YES (BTC in $87,500-$87,749.99)
    Buy: Lower Threshold NO (BTC NOT >= $87,500)
    Buy: Upper Threshold YES (BTC >= $87,750)

    Exactly ONE position pays 100 regardless of where BTC settles.
    If total cost < 100, guaranteed arbitrage profit.
"""

from datetime import datetime
from typing import List, Optional

from backend.services.core.base_strategy import (
    BaseStrategy,
    StrategyType,
    SignalType,
    TradingSignal,
    SignalLeg,
)
from backend.services.btc_arb_scanner import BTCArbitrageScanner, ArbOpportunity
from backend.services.log_config import get_logger

from . import register_strategy

logger = get_logger("btc_arb_strategy")


@register_strategy
class BTCArbitrageStrategy(BaseStrategy):
    """
    BTC range vs threshold arbitrage strategy.

    Wraps BTCArbitrageScanner to integrate with the strategy framework.
    Scans for guaranteed-profit opportunities where buying a combination of
    range YES, lower threshold NO, and upper threshold YES costs < 100 cents.

    Configuration:
        min_edge_percent: Minimum edge to generate signal (default 3.0%)
        scan_interval: Time between scans (default 5 seconds for BTC volatility)
    """

    # Class-level strategy_type for registry
    strategy_type = StrategyType.BTC

    def __init__(
        self,
        kalshi_client,
        min_edge_percent: float = 3.0,
        scan_interval: float = 5.0,
    ):
        """
        Initialize BTCArbitrageStrategy.

        Args:
            kalshi_client: KalshiClient instance for market data
            min_edge_percent: Minimum arbitrage edge to report (default 3.0%)
            scan_interval: Seconds between scans (default 5.0)
        """
        super().__init__(StrategyType.BTC, "BTC Arbitrage Strategy")

        self.kalshi_client = kalshi_client
        self.min_edge_percent = min_edge_percent
        self._scan_interval = scan_interval

        # Initialize the underlying scanner
        self.scanner = BTCArbitrageScanner(kalshi_client)

        logger.info(
            f"BTCArbitrageStrategy initialized: min_edge={min_edge_percent}%, "
            f"scan_interval={scan_interval}s"
        )

    @property
    def scan_interval_seconds(self) -> float:
        """BTC markets scan every 5 seconds by default (high volatility)."""
        return self._scan_interval

    async def scan(self) -> List[TradingSignal]:
        """
        Scan for BTC arbitrage opportunities.

        Delegates to BTCArbitrageScanner and converts ArbOpportunity
        objects to TradingSignal format.

        Returns:
            List of TradingSignal objects for profitable arbitrage opportunities
        """
        signals: List[TradingSignal] = []

        try:
            # Run the underlying scanner
            opportunities = await self.scanner.scan(
                min_edge_percent=self.min_edge_percent
            )

            # Convert each opportunity to a TradingSignal
            for opp in opportunities:
                signal = self._opportunity_to_signal(opp)
                if signal:
                    signals.append(signal)

            if signals:
                logger.info(
                    f"BTC scan found {len(signals)} arbitrage opportunities. "
                    f"Best edge: {signals[0].edge_percent:.1f}%"
                )
            else:
                # Log near-misses from scanner stats
                last_result = self.scanner.get_last_scan_result()
                if last_result and last_result.stats.get("near_misses", 0) > 0:
                    logger.debug(
                        f"No arb, but {last_result.stats['near_misses']} near-misses"
                    )

        except Exception as e:
            logger.error(f"BTC scan error: {e}")

        return signals

    async def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Validate a BTC arbitrage signal before execution.

        Re-fetches current market prices and verifies the arbitrage
        still exists with acceptable edge.
        """
        if not signal.is_arbitrage or len(signal.legs) != 3:
            logger.warning("Invalid signal format for BTC arbitrage")
            return False

        total_cost = 0

        for leg in signal.legs:
            try:
                market = await self.kalshi_client.get_market(leg.ticker)
                if not market:
                    logger.warning(f"Market not found: {leg.ticker}")
                    return False

                # Get current price based on side
                if leg.side == "yes":
                    current_price = market.get("yes_ask")
                else:
                    # NO price = 100 - YES bid
                    yes_bid = market.get("yes_bid")
                    current_price = 100 - yes_bid if yes_bid else None

                if current_price is None:
                    logger.warning(f"No price available for {leg.ticker}")
                    return False

                # Check for significant price movement (> 3 cents)
                if abs(current_price - leg.price_cents) > 3:
                    logger.info(
                        f"Price moved for {leg.ticker}: "
                        f"{leg.price_cents} -> {current_price} (delta > 3)"
                    )
                    return False

                total_cost += current_price

            except Exception as e:
                logger.error(f"Error validating leg {leg.ticker}: {e}")
                return False

        # Must still be profitable
        if total_cost >= 100:
            logger.info(f"Arbitrage no longer profitable: cost {total_cost}c >= 100c")
            return False

        # Edge must still meet threshold (allow some slippage)
        edge_percent = ((100 - total_cost) / total_cost) * 100
        min_threshold = self.min_edge_percent * 0.7  # Allow 30% slippage

        if edge_percent < min_threshold:
            logger.info(
                f"Edge below threshold: {edge_percent:.1f}% < {min_threshold:.1f}%"
            )
            return False

        logger.info(f"Signal validated: total_cost={total_cost}c, edge={edge_percent:.1f}%")
        return True

    def _opportunity_to_signal(self, opp: ArbOpportunity) -> Optional[TradingSignal]:
        """
        Convert ArbOpportunity from scanner to TradingSignal.

        Args:
            opp: ArbOpportunity from BTCArbitrageScanner

        Returns:
            TradingSignal or None if conversion fails
        """
        if not opp.legs or len(opp.legs) != 3:
            logger.warning(f"Invalid opportunity: expected 3 legs, got {len(opp.legs)}")
            return None

        # Convert ArbLeg to SignalLeg
        signal_legs = []
        for leg in opp.legs:
            signal_legs.append(
                SignalLeg(
                    ticker=leg.ticker,
                    side=leg.side,
                    action=leg.action,
                    price_cents=leg.price_cents,
                    strike=leg.strike,
                    lower_bound=leg.lower_bound,
                    upper_bound=leg.upper_bound,
                    description=f"BTC {leg.market_type} {leg.side.upper()}",
                )
            )

        # Use the range market's event date as the primary ticker
        primary_ticker = opp.legs[0].ticker if opp.legs else opp.id

        signal = TradingSignal.create(
            strategy_type=StrategyType.BTC,
            ticker=primary_ticker,
            signal_type=SignalType.ARBITRAGE,
            edge_percent=opp.edge_percent,
            model_prob=1.0,  # Guaranteed profit (arbitrage)
            market_price=opp.total_cost_cents,
            recommended_size=1,
            confidence=1.0,
            is_arbitrage=True,
            legs=signal_legs,
            expires_in_seconds=60,  # BTC prices move fast, short expiry
            metadata={
                "opportunity_id": opp.id,
                "event_date": opp.event_date,
                "settlement_time": opp.settlement_time,
                "total_cost_cents": opp.total_cost_cents,
                "guaranteed_payout_cents": opp.guaranteed_payout_cents,
                "edge_cents": opp.edge_cents,
                "range_description": opp.range_description,
                "detected_at": opp.detected_at,
            },
        )

        return signal

    def get_scanner_stats(self) -> dict:
        """
        Get statistics from the underlying scanner.

        Returns:
            Dict with scan count, last duration, etc.
        """
        return self.scanner.get_stats()

    def get_last_scan_result(self):
        """
        Get the last scan result from the underlying scanner.

        Returns:
            ScanResult object or None
        """
        return self.scanner.get_last_scan_result()
