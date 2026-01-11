"""
Weather Bracket Arbitrage Strategy.

Scans weather markets for bracket arbitrage opportunities and directional
trades based on NWS forecast probabilities.

Key Features:
- Scans all 7 cities (NYC, LAX, CHI, MIA, DEN, AUS, PHL) for both high and low temp series
- Uses NWS forecasts with location-specific adjustments
- Supports bracket arbitrage (all-YES, all-NO, min-2-NO strategies)
- Directional trades when model probability diverges from market price
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import math

from backend.services.core.base_strategy import (
    BaseStrategy,
    StrategyType,
    SignalType,
    TradingSignal,
    SignalLeg,
)
from backend.services.nws_client import NWSClient
from backend.config.locations.registry import get_all_locations, get_location
from backend.config.locations.base import LocationConfig
from backend.services.log_config import get_logger

from . import register_strategy

logger = get_logger("weather_strategy")


@register_strategy
class WeatherStrategy(BaseStrategy):
    """
    Weather bracket arbitrage and directional trading strategy.

    Scans weather markets for:
    1. Bracket arbitrage opportunities (mutually exclusive temperature brackets)
    2. Directional trades when NWS forecast probability diverges from market price

    Configuration:
        min_edge_percent: Minimum edge to generate signal (default 3.0%)
        min_directional_edge: Minimum edge for directional trades (default 5.0%)
        scan_interval: Time between scans (default 30 seconds)
    """

    # Class-level strategy_type for registry
    strategy_type = StrategyType.WEATHER

    def __init__(
        self,
        kalshi_client,
        nws_client: Optional[NWSClient] = None,
        min_edge_percent: float = 3.0,
        min_directional_edge: float = 5.0,
        scan_interval: float = 30.0,
    ):
        """
        Initialize WeatherStrategy.

        Args:
            kalshi_client: KalshiClient instance for market data
            nws_client: Optional NWSClient instance (created if not provided)
            min_edge_percent: Minimum arbitrage edge to report (default 3.0%)
            min_directional_edge: Minimum edge for directional trades (default 5.0%)
            scan_interval: Seconds between scans (default 30.0)
        """
        super().__init__(StrategyType.WEATHER, "Weather Bracket Strategy")

        self.kalshi_client = kalshi_client
        self.nws_client = nws_client or NWSClient()
        self.min_edge_percent = min_edge_percent
        self.min_directional_edge = min_directional_edge
        self._scan_interval = scan_interval

        # Cache for forecasts (refreshed each scan)
        self._forecast_cache: Dict[str, Dict] = {}

        logger.info(
            f"WeatherStrategy initialized: min_edge={min_edge_percent}%, "
            f"scan_interval={scan_interval}s"
        )

    @property
    def scan_interval_seconds(self) -> float:
        """Weather markets scan every 30 seconds by default."""
        return self._scan_interval

    async def scan(self) -> List[TradingSignal]:
        """
        Scan all weather markets for arbitrage and directional opportunities.

        Returns:
            List of TradingSignal objects for profitable opportunities
        """
        signals: List[TradingSignal] = []

        # Get all locations
        locations = get_all_locations()
        logger.info(f"Scanning {len(locations)} locations for weather opportunities")

        for location in locations:
            try:
                # Fetch forecast for this location
                forecast = await self._get_forecast(location)
                if not forecast:
                    logger.warning(f"No forecast available for {location.code}")
                    continue

                # Scan both high and low series
                for series_type in ["high", "low"]:
                    series_ticker = (
                        location.high_series
                        if series_type == "high"
                        else location.low_series
                    )

                    # Get forecast value and uncertainty
                    forecast_temp = forecast.get(series_type)
                    if forecast_temp is None:
                        continue

                    # Calculate uncertainty from location config
                    description = forecast.get(f"{series_type}_description", "")
                    uncertainty = location.calculate_uncertainty(
                        description, is_high=(series_type == "high")
                    )

                    # Fetch markets for this series
                    markets = await self._fetch_series_markets(series_ticker)
                    if not markets:
                        continue

                    # Check for bracket arbitrage
                    arb_signals = self._check_bracket_arbitrage(
                        markets, location, series_type, forecast_temp, uncertainty
                    )
                    signals.extend(arb_signals)

                    # Check for directional opportunities
                    dir_signals = self._check_directional_opportunities(
                        markets, location, series_type, forecast_temp, uncertainty
                    )
                    signals.extend(dir_signals)

            except Exception as e:
                logger.error(f"Error scanning {location.code}: {e}")
                continue

        logger.info(f"Weather scan complete: {len(signals)} signals generated")
        return signals

    async def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Validate a signal before execution.

        Re-checks market prices to ensure the opportunity still exists.
        """
        if signal.is_arbitrage:
            # For arbitrage, verify all leg prices are still valid
            total_cost = 0
            for leg in signal.legs:
                # Fetch current market data
                try:
                    market = await self.kalshi_client.get_market(leg.ticker)
                    if not market:
                        logger.warning(f"Market not found: {leg.ticker}")
                        return False

                    # Get current price
                    if leg.side == "yes":
                        current_price = market.get("yes_ask")
                    else:
                        # NO price = 100 - YES bid
                        yes_bid = market.get("yes_bid")
                        current_price = 100 - yes_bid if yes_bid else None

                    if current_price is None:
                        logger.warning(f"No price for {leg.ticker}")
                        return False

                    # Check if price moved too much (> 2 cents)
                    if abs(current_price - leg.price_cents) > 2:
                        logger.info(
                            f"Price moved for {leg.ticker}: "
                            f"{leg.price_cents} -> {current_price}"
                        )
                        return False

                    total_cost += current_price

                except Exception as e:
                    logger.error(f"Error validating leg {leg.ticker}: {e}")
                    return False

            # Verify still profitable
            if total_cost >= 100:
                logger.info(f"Arbitrage no longer profitable: cost {total_cost}")
                return False

            return True
        else:
            # For directional trades, verify edge still exists
            try:
                market = await self.kalshi_client.get_market(signal.ticker)
                if not market:
                    return False

                current_price = market.get("yes_ask", 0)
                edge = (signal.model_prob * 100 - current_price) / current_price * 100

                # Edge must still be above threshold
                return edge >= self.min_directional_edge * 0.8  # 80% of threshold

            except Exception as e:
                logger.error(f"Error validating directional signal: {e}")
                return False

    async def _get_forecast(self, location: LocationConfig) -> Optional[Dict]:
        """
        Fetch and cache NWS forecast for a location.

        Returns dict with:
            high: High temperature forecast (int)
            low: Low temperature forecast (int)
            high_description: Short forecast for daytime
            low_description: Short forecast for nighttime
        """
        cache_key = location.code

        # Check cache (valid for this scan cycle)
        if cache_key in self._forecast_cache:
            return self._forecast_cache[cache_key]

        # Fetch from NWS
        forecast = await self.nws_client.get_forecast(
            lat=location.latitude,
            lon=location.longitude,
            location_code=location.code,
        )

        if forecast:
            # Apply location-specific adjustments
            if forecast.get("high") is not None:
                forecast["high_adjusted"] = location.adjust_forecast(
                    forecast["high"],
                    forecast.get("high_description", ""),
                    is_high=True,
                )
            if forecast.get("low") is not None:
                forecast["low_adjusted"] = location.adjust_forecast(
                    forecast["low"],
                    forecast.get("low_description", ""),
                    is_high=False,
                )

            self._forecast_cache[cache_key] = forecast

        return forecast

    async def _fetch_series_markets(self, series_ticker: str) -> List[Dict]:
        """Fetch all markets for a weather series."""
        try:
            events = await self.kalshi_client.get_events(
                series_ticker=series_ticker,
                status="open",
                with_nested_markets=True,
                limit=20,
            )

            markets = []
            for event in events:
                for market in event.get("markets", []):
                    market["_event_ticker"] = event.get("event_ticker", "")
                    markets.append(market)

            return markets

        except Exception as e:
            logger.error(f"Error fetching {series_ticker} markets: {e}")
            return []

    def _check_bracket_arbitrage(
        self,
        markets: List[Dict],
        location: LocationConfig,
        series_type: str,
        forecast_temp: float,
        uncertainty: float,
    ) -> List[TradingSignal]:
        """
        Check for bracket arbitrage opportunities.

        Three strategies:
        1. All YES: Buy YES on all brackets if sum < 100
        2. All NO: Buy NO on all brackets if sum < (n-1)*100
        3. Min 2-NO: Buy 2 cheapest NOs if sum < 100
        """
        signals = []

        # Group markets by event (brackets within same event are mutually exclusive)
        by_event: Dict[str, List[Dict]] = {}
        for mkt in markets:
            event_ticker = mkt.get("_event_ticker", "")
            if event_ticker:
                if event_ticker not in by_event:
                    by_event[event_ticker] = []
                by_event[event_ticker].append(mkt)

        for event_ticker, brackets in by_event.items():
            if len(brackets) < 2:
                continue

            # Extract prices
            yes_asks = []
            no_asks = []

            for mkt in brackets:
                yes_ask = mkt.get("yes_ask")
                yes_bid = mkt.get("yes_bid")

                if yes_ask is not None:
                    yes_asks.append((mkt, yes_ask))
                if yes_bid is not None:
                    no_ask = 100 - yes_bid
                    no_asks.append((mkt, no_ask))

            # Strategy 1: All YES
            if yes_asks:
                total_yes = sum(price for _, price in yes_asks)
                if total_yes < 100:
                    edge_cents = 100 - total_yes
                    edge_percent = (edge_cents / total_yes) * 100

                    if edge_percent >= self.min_edge_percent:
                        legs = [
                            SignalLeg(
                                ticker=mkt["ticker"],
                                side="yes",
                                action="buy",
                                price_cents=price,
                                lower_bound=mkt.get("floor_strike"),
                                upper_bound=mkt.get("cap_strike"),
                                description=f"{location.code} {series_type} bracket",
                            )
                            for mkt, price in yes_asks
                        ]

                        signal = TradingSignal.create(
                            strategy_type=StrategyType.WEATHER,
                            ticker=event_ticker,
                            signal_type=SignalType.ARBITRAGE,
                            edge_percent=edge_percent,
                            model_prob=1.0,  # Guaranteed profit
                            market_price=total_yes,
                            recommended_size=1,
                            confidence=1.0,
                            is_arbitrage=True,
                            legs=legs,
                            metadata={
                                "location": location.code,
                                "series_type": series_type,
                                "strategy": "all_yes",
                                "total_cost_cents": total_yes,
                                "guaranteed_payout": 100,
                            },
                        )
                        signals.append(signal)
                        logger.info(
                            f"[{location.code}] All-YES arb: {edge_percent:.1f}% edge"
                        )

            # Strategy 2: All NO
            n = len(no_asks)
            if n >= 2:
                total_no = sum(price for _, price in no_asks)
                max_payout = (n - 1) * 100  # n-1 brackets will be NO

                if total_no < max_payout:
                    edge_cents = max_payout - total_no
                    edge_percent = (edge_cents / total_no) * 100

                    if edge_percent >= self.min_edge_percent:
                        legs = [
                            SignalLeg(
                                ticker=mkt["ticker"],
                                side="no",
                                action="buy",
                                price_cents=price,
                                lower_bound=mkt.get("floor_strike"),
                                upper_bound=mkt.get("cap_strike"),
                                description=f"{location.code} {series_type} bracket NO",
                            )
                            for mkt, price in no_asks
                        ]

                        signal = TradingSignal.create(
                            strategy_type=StrategyType.WEATHER,
                            ticker=event_ticker,
                            signal_type=SignalType.ARBITRAGE,
                            edge_percent=edge_percent,
                            model_prob=1.0,
                            market_price=total_no,
                            recommended_size=1,
                            confidence=1.0,
                            is_arbitrage=True,
                            legs=legs,
                            metadata={
                                "location": location.code,
                                "series_type": series_type,
                                "strategy": "all_no",
                                "total_cost_cents": total_no,
                                "guaranteed_payout": max_payout,
                            },
                        )
                        signals.append(signal)
                        logger.info(
                            f"[{location.code}] All-NO arb: {edge_percent:.1f}% edge"
                        )

            # Strategy 3: Min 2-NO
            if len(no_asks) >= 2:
                # Sort by price, take 2 cheapest
                sorted_nos = sorted(no_asks, key=lambda x: x[1])
                cheapest_two = sorted_nos[:2]
                total_two = sum(price for _, price in cheapest_two)

                if total_two < 100:
                    edge_cents = 100 - total_two
                    edge_percent = (edge_cents / total_two) * 100

                    if edge_percent >= self.min_edge_percent:
                        legs = [
                            SignalLeg(
                                ticker=mkt["ticker"],
                                side="no",
                                action="buy",
                                price_cents=price,
                                lower_bound=mkt.get("floor_strike"),
                                upper_bound=mkt.get("cap_strike"),
                                description=f"{location.code} {series_type} min-2-NO",
                            )
                            for mkt, price in cheapest_two
                        ]

                        signal = TradingSignal.create(
                            strategy_type=StrategyType.WEATHER,
                            ticker=event_ticker,
                            signal_type=SignalType.ARBITRAGE,
                            edge_percent=edge_percent,
                            model_prob=1.0,
                            market_price=total_two,
                            recommended_size=1,
                            confidence=1.0,
                            is_arbitrage=True,
                            legs=legs,
                            metadata={
                                "location": location.code,
                                "series_type": series_type,
                                "strategy": "min_2_no",
                                "total_cost_cents": total_two,
                                "guaranteed_payout": 100,
                            },
                        )
                        signals.append(signal)
                        logger.info(
                            f"[{location.code}] Min-2-NO arb: {edge_percent:.1f}% edge"
                        )

        return signals

    def _check_directional_opportunities(
        self,
        markets: List[Dict],
        location: LocationConfig,
        series_type: str,
        forecast_temp: float,
        uncertainty: float,
    ) -> List[TradingSignal]:
        """
        Check for directional trading opportunities.

        Uses normal distribution probability model to find mispriced brackets.
        """
        signals = []

        for mkt in markets:
            ticker = mkt.get("ticker", "")
            floor_strike = mkt.get("floor_strike")
            cap_strike = mkt.get("cap_strike")

            if floor_strike is None or cap_strike is None:
                continue

            # Calculate model probability using normal distribution
            model_prob = self._calculate_bracket_probability(
                forecast_temp, uncertainty, floor_strike, cap_strike
            )

            # Get market price
            yes_ask = mkt.get("yes_ask")
            if yes_ask is None or yes_ask <= 0:
                continue

            market_prob = yes_ask / 100.0

            # Calculate edge
            edge_percent = ((model_prob - market_prob) / market_prob) * 100

            # Only signal if edge exceeds threshold
            if abs(edge_percent) >= self.min_directional_edge:
                if edge_percent > 0:
                    # Model says more likely than market - buy YES
                    signal_type = SignalType.BUY_YES
                    side = "yes"
                    price = yes_ask
                else:
                    # Model says less likely - buy NO
                    signal_type = SignalType.BUY_NO
                    side = "no"
                    yes_bid = mkt.get("yes_bid")
                    price = 100 - yes_bid if yes_bid else None
                    edge_percent = abs(edge_percent)

                if price is None:
                    continue

                # Calculate confidence based on how far from forecast
                mid_bracket = (floor_strike + cap_strike) / 2
                distance = abs(forecast_temp - mid_bracket)
                confidence = max(0.5, 1.0 - (distance / (uncertainty * 3)))

                signal = TradingSignal.create(
                    strategy_type=StrategyType.WEATHER,
                    ticker=ticker,
                    signal_type=signal_type,
                    edge_percent=edge_percent,
                    model_prob=model_prob,
                    market_price=price,
                    recommended_size=1,
                    confidence=confidence,
                    is_arbitrage=False,
                    legs=[
                        SignalLeg(
                            ticker=ticker,
                            side=side,
                            action="buy",
                            price_cents=price,
                            lower_bound=floor_strike,
                            upper_bound=cap_strike,
                            description=f"{location.code} {series_type} directional",
                        )
                    ],
                    metadata={
                        "location": location.code,
                        "series_type": series_type,
                        "forecast_temp": forecast_temp,
                        "uncertainty": uncertainty,
                        "floor_strike": floor_strike,
                        "cap_strike": cap_strike,
                    },
                )
                signals.append(signal)
                logger.debug(
                    f"[{location.code}] Directional: {ticker} {side} "
                    f"edge={edge_percent:.1f}%"
                )

        return signals

    def _calculate_bracket_probability(
        self,
        forecast: float,
        std_dev: float,
        lower: float,
        upper: float,
    ) -> float:
        """
        Calculate probability that actual temp falls in bracket.

        Uses cumulative normal distribution.

        Args:
            forecast: Forecast temperature
            std_dev: Forecast uncertainty (standard deviation)
            lower: Lower bound of bracket
            upper: Upper bound of bracket

        Returns:
            Probability between 0 and 1
        """
        if std_dev <= 0:
            # Degenerate case - return 1 if forecast in range, else 0
            return 1.0 if lower <= forecast <= upper else 0.0

        # Standard normal CDF approximation
        def norm_cdf(x: float) -> float:
            """Approximate CDF of standard normal distribution."""
            # Abramowitz and Stegun approximation
            a1 = 0.254829592
            a2 = -0.284496736
            a3 = 1.421413741
            a4 = -1.453152027
            a5 = 1.061405429
            p = 0.3275911

            sign = 1 if x >= 0 else -1
            x = abs(x) / math.sqrt(2)

            t = 1.0 / (1.0 + p * x)
            y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(
                -x * x
            )

            return 0.5 * (1.0 + sign * y)

        # Convert to z-scores
        z_lower = (lower - forecast) / std_dev
        z_upper = (upper - forecast) / std_dev

        # P(lower <= X <= upper) = CDF(upper) - CDF(lower)
        prob = norm_cdf(z_upper) - norm_cdf(z_lower)

        return max(0.0, min(1.0, prob))

    def clear_forecast_cache(self) -> None:
        """Clear the forecast cache (call at start of each scan cycle)."""
        self._forecast_cache.clear()
