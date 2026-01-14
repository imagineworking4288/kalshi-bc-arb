"""
Weather Arbitrage Scanner

Scans Kalshi weather markets for bracket arbitrage opportunities.
Handles BOTH high and low temperature markets (14 total series).
"""

import asyncio
import sys
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

# Import configurations
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config.locations import get_all_locations, LocationConfig
from backend.services.core.fee_calculator import FeeCalculator
from backend.services.nws_client import NWSClient
from backend.services.arbitrage_calculator import ArbitrageCalculator
from backend.services.log_config import get_logger

logger = get_logger("weather_arb")

@dataclass
class WeatherOpportunity:
    """A weather arbitrage opportunity."""
    city_code: str
    city_name: str
    market_type: str  # "high" or "low"
    series_ticker: str
    event_ticker: str
    total_cost: int
    gross_profit: int
    net_profit: int
    bracket_count: int
    brackets: List[Dict]
    forecast_temp: Optional[int]
    forecast_uncertainty: float
    found_at: str

    def to_dict(self) -> Dict:
        return {
            "city_code": self.city_code,
            "city_name": self.city_name,
            "market_type": self.market_type,
            "series_ticker": self.series_ticker,
            "event_ticker": self.event_ticker,
            "total_cost": self.total_cost,
            "gross_profit": self.gross_profit,
            "net_profit": self.net_profit,
            "bracket_count": self.bracket_count,
            "brackets": self.brackets,
            "forecast_temp": self.forecast_temp,
            "forecast_uncertainty": self.forecast_uncertainty,
            "found_at": self.found_at
        }

class WeatherArbScanner:
    """
    Scanner for weather bracket arbitrage.

    Scans all 7 cities × 2 types = 14 market series.
    """

    def __init__(self, kalshi_client):
        self.kalshi = kalshi_client
        self.nws = NWSClient()
        self.locations = get_all_locations()
        self.arb_calculator = ArbitrageCalculator()

        # Results storage
        self.scan_count = 0
        self.last_scan: Optional[str] = None
        self.running = False

        # Results by city (nested high/low)
        self.city_results: Dict[str, Dict] = {}

        # All opportunities and near-misses
        self.opportunities: List[Dict] = []
        self.near_misses: List[Dict] = []

        # Forecasts cache
        self.forecasts: Dict[str, Dict] = {}

        logger.info(f"Weather scanner initialized: {len(self.locations)} cities × 2 types = {len(self.locations) * 2} series")

    async def scan_once(self) -> Dict:
        """Run a single scan of all weather markets."""
        self.scan_count += 1
        self.last_scan = datetime.now().isoformat()

        logger.info(f"[SCAN] Starting weather scan #{self.scan_count} ({len(self.locations)} cities × 2 types)")

        # Clear previous results
        self.opportunities = []
        self.near_misses = []
        self.city_results = {}

        total_brackets = {"high": 0, "low": 0}

        # Scan each city
        for location in self.locations:
            city_result = {
                "code": location.code,
                "city": location.city,
                "high": None,
                "low": None
            }

            # Fetch NWS forecast (returns both high and low)
            try:
                forecast = await self.nws.get_forecast(
                    location.latitude,
                    location.longitude,
                    location.code
                )
                self.forecasts[location.code] = forecast
            except Exception as e:
                logger.warning(f"[{location.code}] Forecast fetch failed: {e}")
                forecast = None

            # Scan HIGH temperature markets
            high_result = await self._analyze_series(
                location,
                location.high_series,
                "high",
                forecast
            )
            city_result["high"] = high_result
            total_brackets["high"] += high_result.get("bracket_count", 0)

            # Scan LOW temperature markets
            low_result = await self._analyze_series(
                location,
                location.low_series,
                "low",
                forecast
            )
            city_result["low"] = low_result
            total_brackets["low"] += low_result.get("bracket_count", 0)

            self.city_results[location.code] = city_result

        # Build summary
        total_arb = len(self.opportunities)
        total_near = len(self.near_misses)

        logger.info(
            f"[SCAN] Scanned {total_brackets['high'] + total_brackets['low']} brackets "
            f"(HIGH: {total_brackets['high']}, LOW: {total_brackets['low']}) - "
            f"{total_arb} opportunities, {total_near} near-misses"
        )

        return self.get_status()

    async def _analyze_series(
        self,
        location: LocationConfig,
        series_ticker: str,
        market_type: str,
        forecast: Optional[Dict]
    ) -> Dict:
        """
        Analyze a single series (high or low) for arbitrage.

        Args:
            location: Location configuration
            series_ticker: e.g., "KXHIGHNY" or "KXLOWNY"
            market_type: "high" or "low"
            forecast: NWS forecast data
        """
        result = {
            "series": series_ticker,
            "market_type": market_type,
            "bracket_count": 0,
            "brackets": [],
            "best_cost": None,
            "totals": None,
            "arbitrage": None,
            "opportunities": [],
            "near_misses": [],
            "forecast": None,
            "error": None
        }

        try:
            # Get events for this series
            events = await self.kalshi.get_events(series_ticker=series_ticker, status="open")

            if not events:
                result["error"] = "No open events"
                return result

            # Select TODAY's event using hybrid approach:
            # 1. Try to match today's date string in event_ticker
            # 2. Fall back to sorting by close_time (pick soonest)
            today_event = None
            today_str = date.today().strftime("%y%b%d").upper()  # e.g., "26JAN13"

            # Try date string matching first
            for evt in events:
                event_ticker = evt.get("event_ticker", "")
                if today_str in event_ticker:
                    today_event = evt
                    break

            # Fallback: sort by close_time and pick soonest
            if today_event is None:
                events_sorted = sorted(
                    events,
                    key=lambda e: e.get("close_time") or e.get("expiration_time") or "",
                    reverse=False  # Ascending = soonest first
                )
                today_event = events_sorted[0] if events_sorted else events[-1]
                logger.warning(
                    f"No event for today ({today_str}), using soonest: {today_event.get('event_ticker')}"
                )

            # Process selected event
            for event in [today_event]:
                event_ticker = event.get("event_ticker", "")

                # Get markets for this event - use series_ticker instead
                markets = []
                try:
                    # Try to get markets from the event
                    if "markets" in event:
                        markets = event["markets"]
                    else:
                        # Fallback: fetch markets separately
                        markets_data = await self.kalshi.get_markets(limit=1000)
                        # Filter for this series
                        markets = [m for m in markets_data if m.get("series_ticker") == series_ticker]
                except Exception as e:
                    logger.warning(f"[{location.code}] Failed to get markets: {e}")

                if not markets:
                    continue

                result["bracket_count"] = len(markets)

                # Calculate total cost to buy YES on all brackets
                total_cost = 0
                brackets = []

                for market in markets:
                    yes_ask = market.get("yes_ask", 0) or 0
                    no_ask = market.get("no_ask", 0) or 0
                    total_cost += yes_ask

                    brackets.append({
                        "ticker": market.get("ticker"),
                        "title": market.get("title", ""),
                        "floor_strike": market.get("floor_strike"),
                        "cap_strike": market.get("cap_strike"),
                        "yes_ask": yes_ask,
                        "yes_bid": market.get("yes_bid", 0) or 0,
                        "no_ask": no_ask,
                        "no_bid": market.get("no_bid", 0) or 0,
                        "volume": market.get("volume", 0) or 0
                    })

                result["brackets"] = brackets
                result["best_cost"] = total_cost

                # Calculate totals
                result["totals"] = {
                    "yes_ask": sum(b["yes_ask"] for b in brackets),
                    "yes_bid": sum(b["yes_bid"] for b in brackets),
                    "no_ask": sum(b["no_ask"] for b in brackets),
                    "no_bid": sum(b["no_bid"] for b in brackets),
                    "volume": sum(b["volume"] for b in brackets)
                }

                # Run arbitrage analysis with all 3 strategies
                result["arbitrage"] = self.arb_calculator.analyze(brackets)

                # Get forecast temperature
                forecast_temp = None
                forecast_desc = ""
                if forecast:
                    if market_type == "high":
                        forecast_temp = forecast.get("high")
                        forecast_desc = forecast.get("high_description", "")
                    else:
                        forecast_temp = forecast.get("low")
                        forecast_desc = forecast.get("low_description", "")

                    # Adjust forecast
                    if forecast_temp:
                        adjusted_temp = location.adjust_forecast(forecast_temp, forecast_desc, is_high=(market_type == "high"))
                        uncertainty = location.calculate_uncertainty(forecast_desc, is_high=(market_type == "high"))
                        result["forecast"] = {
                            "raw_temp": forecast_temp,
                            "adjusted_temp": adjusted_temp,
                            "uncertainty": uncertainty,
                            "description": forecast_desc
                        }
                        forecast_temp = adjusted_temp

                # Check for arbitrage (total cost < 100 cents)
                if total_cost > 0 and total_cost < 100:
                    gross, fees, net = FeeCalculator.calculate_arbitrage_profit(total_cost)

                    opp = WeatherOpportunity(
                        city_code=location.code,
                        city_name=location.city,
                        market_type=market_type,
                        series_ticker=series_ticker,
                        event_ticker=event_ticker,
                        total_cost=total_cost,
                        gross_profit=gross,
                        net_profit=net,
                        bracket_count=len(brackets),
                        brackets=brackets,
                        forecast_temp=forecast_temp,
                        forecast_uncertainty=result.get("forecast", {}).get("uncertainty", 3.0),
                        found_at=datetime.now().isoformat()
                    )

                    result["opportunities"].append(opp.to_dict())
                    self.opportunities.append(opp.to_dict())

                    logger.info(
                        f"[OK] ARB [{market_type.upper()}]: {location.city} {event_ticker} - "
                        f"Cost: {total_cost}¢, Net: {net}¢"
                    )

                # Check for near-miss (within 5 cents of arbitrage)
                elif total_cost > 0 and total_cost <= 105:
                    near_miss = {
                        "city_code": location.code,
                        "city_name": location.city,
                        "market_type": market_type,
                        "series_ticker": series_ticker,
                        "event_ticker": event_ticker,
                        "total_cost": total_cost,
                        "distance": total_cost - 100,
                        "bracket_count": len(brackets)
                    }
                    result["near_misses"].append(near_miss)
                    self.near_misses.append(near_miss)

                    logger.info(
                        f"[HOT] Near [{market_type.upper()}]: {location.city} at {total_cost}¢ "
                        f"({total_cost - 100}¢ away)"
                    )

        except Exception as e:
            logger.error(f"[{location.code}] Error scanning {series_ticker}: {e}")
            result["error"] = str(e)

        return result

    def get_status(self) -> Dict:
        """Get full scanner status."""
        return {
            "running": self.running,
            "scan_count": self.scan_count,
            "last_scan": self.last_scan,
            "cities": self.city_results,
            "opportunities": self.opportunities,
            "near_misses": self.near_misses,
            "forecasts": self.forecasts,
            "stats": {
                "total_cities": len(self.locations),
                "total_series": len(self.locations) * 2,
                "total_arbitrage": len(self.opportunities),
                "total_near_miss": len(self.near_misses),
                "best_cost": min(
                    (o["total_cost"] for o in self.opportunities),
                    default=min(
                        (n["total_cost"] for n in self.near_misses),
                        default=None
                    )
                )
            }
        }
