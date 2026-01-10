"""
Prediction API routes for weather forecasting and bracket probability analysis.

Addresses Issues #11-#13:
- #11: Rate limiting via FastAPI dependencies
- #12: Pydantic request validation
- #13: Cache-Control headers
"""

from fastapi import APIRouter, HTTPException, Query, Response, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import asyncio

from ..services.nws import NWSProductionClient, get_forecast, NWS_GRID_POINTS
from ..services.analysis import (
    PredictionEngineV2,
    BracketAnalysis,
    PredictionResult,
    PositionInfo,
    RecommendationAction,
    get_prediction_engine,
    analyze_brackets,
)
from ..services.kalshi_client import KalshiClient

router = APIRouter(prefix="/predictions", tags=["predictions"])

# Services
_nws_client: Optional[NWSProductionClient] = None
_kalshi_client: Optional[KalshiClient] = None


def get_nws_client() -> NWSProductionClient:
    """Get or create NWS client singleton."""
    global _nws_client
    if _nws_client is None:
        _nws_client = NWSProductionClient()
    return _nws_client


def get_kalshi() -> KalshiClient:
    """Get or create Kalshi client singleton."""
    global _kalshi_client
    if _kalshi_client is None:
        _kalshi_client = KalshiClient()
    return _kalshi_client


# ============== Request/Response Models (Issue #12) ==============

class BracketInput(BaseModel):
    """Input for a single bracket market."""
    ticker: str
    floor_strike: Optional[int] = None
    cap_strike: Optional[int] = None
    yes_price: Optional[int] = Field(None, ge=1, le=99)
    no_price: Optional[int] = Field(None, ge=1, le=99)


class PredictionRequest(BaseModel):
    """Request for bracket predictions."""
    brackets: List[BracketInput]
    forecast_high: int = Field(..., ge=-50, le=150)
    forecast_std_dev: float = Field(default=3.0, ge=0.5, le=10.0)
    event_ticker: str = ""
    positions: List[Dict[str, Any]] = Field(default_factory=list)


class ForecastResponse(BaseModel):
    """Response with forecast data."""
    city: str
    forecast_high: int
    forecast_low: int
    weather_pattern: str
    short_forecast: str
    source: str
    fetched_at: str
    cached: bool
    cache_age_seconds: float


class BracketPredictionResponse(BaseModel):
    """Response for a single bracket prediction."""
    ticker: str
    label: str
    model_probability: float
    market_implied_probability: float
    probability_edge: float
    yes_price_cents: Optional[int]
    no_price_cents: Optional[int]
    yes_ev_after_fee: float
    no_ev_after_fee: float
    recommended_action: str
    recommended_side: Optional[str]
    recommended_contracts: int
    kelly_fraction: float
    has_existing_position: bool
    position_conflict: bool
    confidence: float


class PredictionResponse(BaseModel):
    """Full prediction response."""
    city: str
    event_ticker: str
    forecast: ForecastResponse
    brackets: List[BracketPredictionResponse]
    total_probability: float
    has_opportunities: bool
    best_opportunity: Optional[BracketPredictionResponse]
    warnings: List[str]
    generated_at: str


# ============== Rate Limiting (Issue #11) ==============

class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}

    def check(self, key: str) -> bool:
        """Check if request is allowed."""
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - self.window_seconds

        # Clean old requests
        if key in self._requests:
            self._requests[key] = [t for t in self._requests[key] if t > window_start]
        else:
            self._requests[key] = []

        # Check limit
        if len(self._requests[key]) >= self.max_requests:
            return False

        # Record request
        self._requests[key].append(now)
        return True


_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)


async def rate_limit_check():
    """Dependency for rate limiting."""
    # Use a simple key for now (could be IP-based in production)
    if not _rate_limiter.check("global"):
        raise HTTPException(429, "Rate limit exceeded. Try again later.")


# ============== Helper Functions ==============

def _format_bracket_response(analysis: BracketAnalysis) -> BracketPredictionResponse:
    """Format bracket analysis for API response."""
    return BracketPredictionResponse(
        ticker=analysis.ticker,
        label=analysis.label,
        model_probability=round(analysis.model_probability, 4),
        market_implied_probability=round(analysis.market_implied_probability, 4),
        probability_edge=round(analysis.probability_edge, 4),
        yes_price_cents=analysis.yes_price_cents,
        no_price_cents=analysis.no_price_cents,
        yes_ev_after_fee=round(analysis.yes_ev_after_fee, 2),
        no_ev_after_fee=round(analysis.no_ev_after_fee, 2),
        recommended_action=analysis.recommended_action.value,
        recommended_side=analysis.recommended_side,
        recommended_contracts=analysis.recommended_contracts,
        kelly_fraction=round(analysis.kelly_fraction, 4),
        has_existing_position=analysis.has_existing_position,
        position_conflict=analysis.position_conflict,
        confidence=round(analysis.confidence, 3),
    )


async def _get_city_markets(city: str) -> List[Dict[str, Any]]:
    """Fetch weather bracket markets for a city."""
    kalshi = get_kalshi()

    # Map city to series ticker
    series_map = {
        "NYC": "KXHIGHNY",
        "CHI": "KXHIGHCHI",
        "MIA": "KXHIGHMIA",
        "AUS": "KXHIGHAUS",
        "LAX": "KXHIGHLAX",
        "DEN": "KXHIGHDEN",
        "PHL": "KXHIGHPHL",
    }

    series = series_map.get(city.upper())
    if not series:
        return []

    try:
        events = await kalshi.get_events(
            series_ticker=series,
            status="open",
            with_nested_markets=True,
            limit=5
        )

        markets = []
        for event in events:
            for market in event.get("markets", []):
                markets.append({
                    "ticker": market.get("ticker"),
                    "floor_strike": market.get("floor_strike"),
                    "cap_strike": market.get("cap_strike"),
                    "yes_price": market.get("yes_ask"),
                    "no_price": market.get("no_ask"),
                    "event_ticker": event.get("event_ticker"),
                })
        return markets
    except Exception:
        return []


async def _get_positions_for_city(city: str) -> List[PositionInfo]:
    """Get existing positions for city markets."""
    kalshi = get_kalshi()

    try:
        positions_response = await kalshi.get_portfolio_positions()
        positions = positions_response if isinstance(positions_response, list) else []

        # Filter to weather markets for this city
        city_positions = []
        for pos in positions:
            ticker = pos.get("ticker", "")
            if city.upper() in ticker.upper():
                position_count = pos.get("position", 0)
                side = "yes" if position_count > 0 else "no"
                city_positions.append(PositionInfo(
                    ticker=ticker,
                    side=side,
                    quantity=abs(position_count),
                    avg_cost_cents=pos.get("market_exposure", 0) / max(1, abs(position_count)),
                ))
        return city_positions
    except Exception:
        return []


# ============== Routes ==============

@router.get("/cities")
async def get_supported_cities():
    """Get list of supported cities for weather predictions."""
    cities = []
    for code, grid_point in NWS_GRID_POINTS.items():
        cities.append({
            "code": code,
            "latitude": grid_point.latitude,
            "longitude": grid_point.longitude,
            "timezone": grid_point.timezone,
        })
    return {"cities": cities}


@router.get("/{city}", dependencies=[Depends(rate_limit_check)])
async def get_city_predictions(
    city: str,
    response: Response,
    force_refresh: bool = Query(False, description="Force forecast refresh"),
    include_positions: bool = Query(True, description="Include existing positions"),
) -> PredictionResponse:
    """
    Get weather predictions and trading recommendations for a city.

    Issues addressed:
    - #11: Rate limited
    - #12: Pydantic validation
    - #13: Cache-Control headers
    """
    city = city.upper()

    # Validate city
    if city not in NWS_GRID_POINTS:
        raise HTTPException(404, f"City '{city}' not supported. Use /predictions/cities for list.")

    # Get forecast
    nws = get_nws_client()
    forecast = await nws.get_forecast(city, force_refresh=force_refresh)

    if not forecast:
        raise HTTPException(503, f"Unable to get forecast for {city}")

    # Get cache info
    cache_info = nws.get_cache_info(city)
    cached = cache_info is not None and not force_refresh
    cache_age = cache_info.get("age_seconds", 0) if cache_info else 0

    # Set cache headers (Issue #13)
    if cached:
        response.headers["Cache-Control"] = "public, max-age=60"
        response.headers["X-Cache"] = "HIT"
    else:
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Cache"] = "MISS"

    response.headers["X-Forecast-Source"] = forecast.source
    response.headers["X-Cache-Age"] = str(int(cache_age))

    # Get markets for this city
    markets = await _get_city_markets(city)

    if not markets:
        # Return forecast without predictions if no markets
        return PredictionResponse(
            city=city,
            event_ticker="",
            forecast=ForecastResponse(
                city=city,
                forecast_high=forecast.forecast_high,
                forecast_low=forecast.forecast_low,
                weather_pattern=forecast.weather_pattern,
                short_forecast=forecast.short_forecast,
                source=forecast.source,
                fetched_at=forecast.fetched_at.isoformat(),
                cached=cached,
                cache_age_seconds=cache_age,
            ),
            brackets=[],
            total_probability=0.0,
            has_opportunities=False,
            best_opportunity=None,
            warnings=["No open markets found for this city"],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # Get positions if requested
    positions = []
    if include_positions:
        positions = await _get_positions_for_city(city)

    # Run prediction engine
    engine = get_prediction_engine()

    # Calculate std dev from weather pattern
    std_dev_map = {
        "stable": 1.5,
        "transitional": 3.0,
        "stormy": 4.5,
        "frontal": 5.0,
    }
    forecast_std_dev = std_dev_map.get(forecast.weather_pattern, 3.0)

    # Adjust for confidence
    confidence_multiplier = 1.0 + (1.0 - forecast.confidence_level) * 0.5
    forecast_std_dev *= confidence_multiplier

    # Analyze brackets
    result = engine.analyze_brackets(
        brackets=markets,
        forecast_high=forecast.forecast_high,
        forecast_std_dev=forecast_std_dev,
        positions=positions,
        forecast_source=forecast.source,
        event_ticker=markets[0].get("event_ticker", "") if markets else "",
        city=city,
    )

    # Format response
    bracket_responses = [_format_bracket_response(b) for b in result.brackets]

    best_opportunity = None
    if result.best_bracket:
        best_opportunity = _format_bracket_response(result.best_bracket)

    return PredictionResponse(
        city=city,
        event_ticker=result.event_ticker,
        forecast=ForecastResponse(
            city=city,
            forecast_high=forecast.forecast_high,
            forecast_low=forecast.forecast_low,
            weather_pattern=forecast.weather_pattern,
            short_forecast=forecast.short_forecast,
            source=forecast.source,
            fetched_at=forecast.fetched_at.isoformat(),
            cached=cached,
            cache_age_seconds=cache_age,
        ),
        brackets=bracket_responses,
        total_probability=round(result.total_probability, 4),
        has_opportunities=result.has_opportunities,
        best_opportunity=best_opportunity,
        warnings=result.warnings,
        generated_at=result.generated_at.isoformat(),
    )


@router.get("/{city}/forecast", dependencies=[Depends(rate_limit_check)])
async def get_city_forecast(
    city: str,
    response: Response,
    force_refresh: bool = Query(False),
) -> ForecastResponse:
    """Get just the weather forecast for a city (without predictions)."""
    city = city.upper()

    if city not in NWS_GRID_POINTS:
        raise HTTPException(404, f"City '{city}' not supported")

    nws = get_nws_client()
    forecast = await nws.get_forecast(city, force_refresh=force_refresh)

    if not forecast:
        raise HTTPException(503, f"Unable to get forecast for {city}")

    cache_info = nws.get_cache_info(city)
    cached = cache_info is not None and not force_refresh
    cache_age = cache_info.get("age_seconds", 0) if cache_info else 0

    # Cache headers
    response.headers["Cache-Control"] = "public, max-age=300" if cached else "no-cache"
    response.headers["X-Forecast-Source"] = forecast.source

    return ForecastResponse(
        city=city,
        forecast_high=forecast.forecast_high,
        forecast_low=forecast.forecast_low,
        weather_pattern=forecast.weather_pattern,
        short_forecast=forecast.short_forecast,
        source=forecast.source,
        fetched_at=forecast.fetched_at.isoformat(),
        cached=cached,
        cache_age_seconds=cache_age,
    )


@router.post("/{city}/refresh", dependencies=[Depends(rate_limit_check)])
async def refresh_city_forecast(city: str) -> Dict[str, Any]:
    """Force refresh forecast for a city."""
    city = city.upper()

    if city not in NWS_GRID_POINTS:
        raise HTTPException(404, f"City '{city}' not supported")

    nws = get_nws_client()
    forecast = await nws.get_forecast(city, force_refresh=True)

    if not forecast:
        raise HTTPException(503, f"Unable to refresh forecast for {city}")

    return {
        "success": True,
        "city": city,
        "source": forecast.source,
        "forecast_high": forecast.forecast_high,
        "forecast_low": forecast.forecast_low,
    }


@router.post("/analyze", dependencies=[Depends(rate_limit_check)])
async def analyze_custom_brackets(request: PredictionRequest) -> Dict[str, Any]:
    """
    Analyze custom bracket data with predictions.

    Useful for testing or analyzing hypothetical scenarios.
    """
    # Convert positions
    positions = []
    for pos in request.positions:
        positions.append(PositionInfo(
            ticker=pos.get("ticker", ""),
            side=pos.get("side", "yes"),
            quantity=pos.get("quantity", 0),
        ))

    # Convert brackets
    brackets = [
        {
            "ticker": b.ticker,
            "floor_strike": b.floor_strike,
            "cap_strike": b.cap_strike,
            "yes_price": b.yes_price,
            "no_price": b.no_price,
        }
        for b in request.brackets
    ]

    # Run analysis
    engine = get_prediction_engine()
    result = engine.analyze_brackets(
        brackets=brackets,
        forecast_high=request.forecast_high,
        forecast_std_dev=request.forecast_std_dev,
        positions=positions if positions else None,
        event_ticker=request.event_ticker,
    )

    return {
        "brackets": [
            {
                "ticker": b.ticker,
                "label": b.label,
                "model_probability": round(b.model_probability, 4),
                "probability_edge": round(b.probability_edge, 4),
                "recommended_action": b.recommended_action.value,
                "recommended_contracts": b.recommended_contracts,
                "yes_ev_after_fee": round(b.yes_ev_after_fee, 2),
                "no_ev_after_fee": round(b.no_ev_after_fee, 2),
            }
            for b in result.brackets
        ],
        "total_probability": round(result.total_probability, 4),
        "has_opportunities": result.has_opportunities,
        "warnings": result.warnings,
    }


@router.get("/status")
async def get_prediction_status() -> Dict[str, Any]:
    """Get status of prediction system including API health."""
    nws = get_nws_client()

    return {
        "circuits": nws.get_circuit_status(),
        "supported_cities": list(NWS_GRID_POINTS.keys()),
        "cache_entries": len(nws._cache),
    }


@router.post("/reset-circuits")
async def reset_prediction_circuits() -> Dict[str, Any]:
    """Reset circuit breakers for forecast APIs."""
    nws = get_nws_client()
    nws.reset_circuits()

    return {
        "success": True,
        "circuits": nws.get_circuit_status(),
    }
