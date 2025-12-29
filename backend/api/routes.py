"""FastAPI routes for the arbitrage scanner API"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..config import get_settings
from ..services.analytics_service import AnalyticsService
from ..services.arbitrage_engine import ArbitrageEngine
from ..services.cf_benchmarks_client import CFBenchmarksClient
from ..services.kalshi_client import KalshiClient
from ..services.market_service import MarketService
from ..services.opportunity_logger import OpportunityLogger
from ..services.position_tracker import PositionTracker
from ..services.trade_executor import PositionSizer, TradeExecutor

router = APIRouter()

# Service instances
kalshi = KalshiClient()
cf_benchmarks = CFBenchmarksClient()
market_service = MarketService(kalshi)
arb_engine = ArbitrageEngine()
opp_logger = OpportunityLogger()
analytics = AnalyticsService()
trade_executor = TradeExecutor(kalshi)
position_tracker = PositionTracker()


# Request/Response models
class EnvironmentSwitch(BaseModel):
    environment: str


class TradeRequest(BaseModel):
    opportunity_id: str
    position_size: float


class ConfigResponse(BaseModel):
    environment: str
    kalshi_connected: bool
    spot_prices_enabled: bool


# Helper functions
def _serialize_group(group):
    return {
        "asset": group.asset,
        "settlement_time": group.settlement_time.isoformat(),
        "spot_price": group.spot_price,
        "is_complete": group.is_complete,
        "thresholds": [
            {
                "ticker": t.ticker,
                "title": t.title,
                "strike": t.strike,
                "direction": t.direction,
                "yes_price": t.yes_price,
                "yes_ask": t.yes_ask,
                "yes_bid": t.yes_bid,
                "volume": t.volume
            }
            for t in group.thresholds
        ],
        "brackets": [
            {
                "ticker": b.ticker,
                "title": b.title,
                "low_bound": b.low_bound,
                "high_bound": b.high_bound,
                "yes_price": b.yes_price,
                "yes_ask": b.yes_ask,
                "yes_bid": b.yes_bid,
                "volume": b.volume
            }
            for b in group.brackets
        ]
    }


def _serialize_opportunity(opp):
    return {
        "id": opp.id,
        "asset": opp.asset,
        "settlement_time": opp.settlement_time.isoformat(),
        "detected_at": opp.detected_at.isoformat(),
        "threshold_ticker": opp.threshold_ticker,
        "threshold_title": opp.threshold_title,
        "threshold_strike": opp.threshold_strike,
        "threshold_direction": opp.threshold_direction,
        "threshold_yes_price": opp.threshold_yes_price,
        "implied_price": opp.implied_price,
        "divergence": opp.divergence,
        "gross_profit_pct": opp.gross_profit_pct,
        "estimated_fees": opp.estimated_fees,
        "net_profit_pct": opp.net_profit_pct,
        "spot_price": opp.spot_price,
        "spot_relation": opp.spot_relation,
        "distance_from_threshold": opp.distance_from_threshold,
        "max_liquidity_usd": opp.max_liquidity_usd,
        "max_liquidity_contracts": opp.max_liquidity_contracts,
        "limiting_leg": opp.limiting_leg,
        "trade_direction": opp.trade_direction,
        "score": opp.score,
        "required_brackets": [
            {
                "ticker": b.ticker,
                "title": b.title,
                "low_bound": b.low_bound,
                "high_bound": b.high_bound,
                "yes_price": b.yes_price,
                "yes_ask": b.yes_ask
            }
            for b in opp.required_brackets
        ]
    }


# Configuration endpoints
@router.get("/config")
async def get_config() -> ConfigResponse:
    """Get current configuration"""
    settings = get_settings()
    return ConfigResponse(
        environment=settings.kalshi_env,
        kalshi_connected=kalshi.is_authenticated,
        spot_prices_enabled=True
    )


@router.post("/config/environment")
async def switch_environment(request: EnvironmentSwitch):
    """Switch between demo and production"""
    if request.environment not in ["demo", "production"]:
        raise HTTPException(400, "Invalid environment")
    # Note: In production, this would require a server restart
    return {"status": "ok", "environment": request.environment}


# Market endpoints
@router.get("/markets")
async def get_markets(
    asset: Optional[str] = Query(None, description="Filter by asset")
):
    """Get all grouped markets"""
    try:
        assets = [asset] if asset else None
        groups = await market_service.get_grouped_markets(assets=assets)

        # Add spot prices
        spot_prices = await cf_benchmarks.get_all_prices()
        for group in groups:
            if group.asset in spot_prices:
                group.spot_price = spot_prices[group.asset].price

        return {"groups": [_serialize_group(g) for g in groups]}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch markets: {str(e)}")


# Opportunity endpoints
@router.get("/opportunities")
async def get_opportunities(
    min_profit: float = Query(1.0, description="Minimum profit percentage"),
    asset: Optional[str] = Query(None, description="Filter by asset")
):
    """Get current arbitrage opportunities"""
    try:
        assets = [asset] if asset else None
        groups = await market_service.get_grouped_markets(assets=assets)

        # Add spot prices
        spot_prices = await cf_benchmarks.get_all_prices()
        for group in groups:
            if group.asset in spot_prices:
                group.spot_price = spot_prices[group.asset].price

        # Find opportunities
        arb_engine.min_profit_pct = min_profit
        opportunities = arb_engine.find_opportunities(groups)

        # Filter by asset if specified
        if asset:
            opportunities = [o for o in opportunities if o.asset == asset]

        # Log opportunities
        for opp in opportunities:
            await opp_logger.log_opportunity(opp)

        return {"opportunities": [_serialize_opportunity(o) for o in opportunities]}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch opportunities: {str(e)}")


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity(opportunity_id: str):
    """Get a specific opportunity"""
    opp = await opp_logger.get_opportunity(opportunity_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    return opp


# Spot price endpoints
@router.get("/spot-prices")
async def get_spot_prices():
    """Get current spot prices"""
    prices = await cf_benchmarks.get_all_prices()
    return {
        "prices": {
            asset: {
                "price": p.price,
                "timestamp": p.timestamp.isoformat(),
                "cached": p.cached
            }
            for asset, p in prices.items()
        }
    }


# Account endpoints
@router.get("/balance")
async def get_balance():
    """Get account balance"""
    try:
        balance = await kalshi.get_balance()
        return {
            "available_balance": balance.get("available_balance", 0) / 100,
            "total_balance": balance.get("balance", 0) / 100
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch balance: {str(e)}")


@router.get("/positions")
async def get_positions():
    """Get open positions"""
    try:
        positions = await kalshi.get_positions()
        return {"positions": positions}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch positions: {str(e)}")


# Trading endpoints
@router.post("/trade")
async def execute_trade(request: TradeRequest):
    """Execute an arbitrage trade"""
    try:
        # Get current opportunities
        groups = await market_service.get_grouped_markets()
        spot_prices = await cf_benchmarks.get_all_prices()
        for group in groups:
            if group.asset in spot_prices:
                group.spot_price = spot_prices[group.asset].price

        opportunities = arb_engine.find_opportunities(groups)

        # Find the specific opportunity
        opportunity = next(
            (o for o in opportunities if o.id == request.opportunity_id),
            None
        )

        if not opportunity:
            raise HTTPException(404, "Opportunity not found or expired")

        # Get sizing suggestions
        balance_info = await kalshi.get_balance()
        balance = balance_info.get("available_balance", 0) / 100

        suggestions = PositionSizer.get_suggestions(balance, opportunity)

        # Execute trade
        result = await trade_executor.execute_arbitrage(
            opportunity,
            request.position_size
        )

        # Save trade
        await position_tracker.save_trade(result)

        # Mark opportunity as traded
        if result.status in ["success", "partial"]:
            await opp_logger.mark_traded(opportunity.id, result.trade_id)

        return {
            "result": {
                "trade_id": result.trade_id,
                "status": result.status,
                "total_cost": result.total_cost,
                "total_fees": result.total_fees,
                "expected_payout": result.expected_payout,
                "expected_profit": result.expected_profit,
                "message": result.message,
                "orders": [
                    {
                        "ticker": o.ticker,
                        "order_id": o.order_id,
                        "status": o.status,
                        "filled": o.contracts_filled,
                        "requested": o.contracts_requested
                    }
                    for o in result.orders
                ]
            },
            "sizing_suggestions": suggestions
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Trade failed: {str(e)}")


@router.get("/trade/suggestions/{opportunity_id}")
async def get_trade_suggestions(
    opportunity_id: str,
    position_size: Optional[float] = None
):
    """Get trade sizing suggestions for an opportunity"""
    try:
        # Get current opportunities
        groups = await market_service.get_grouped_markets()
        spot_prices = await cf_benchmarks.get_all_prices()
        for group in groups:
            if group.asset in spot_prices:
                group.spot_price = spot_prices[group.asset].price

        opportunities = arb_engine.find_opportunities(groups)

        opportunity = next(
            (o for o in opportunities if o.id == opportunity_id),
            None
        )

        if not opportunity:
            raise HTTPException(404, "Opportunity not found or expired")

        # Get balance
        balance_info = await kalshi.get_balance()
        balance = balance_info.get("available_balance", 0) / 100

        suggestions = PositionSizer.get_suggestions(balance, opportunity)

        # Calculate trade details if position size provided
        trade_details = None
        if position_size:
            trade_details = arb_engine.calculate_trade_details(
                opportunity, position_size
            )

        return {
            "suggestions": suggestions,
            "balance": balance,
            "trade_details": trade_details
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get suggestions: {str(e)}")


# History endpoints
@router.get("/history/opportunities")
async def get_opportunity_history(
    asset: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_profit: Optional[float] = None,
    traded_only: bool = False,
    limit: int = 100
):
    """Get historical opportunities"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    history = await opp_logger.get_history(
        asset=asset,
        start_date=start,
        end_date=end,
        min_profit=min_profit,
        traded_only=traded_only,
        limit=limit
    )

    return {"opportunities": history}


@router.get("/history/trades")
async def get_trade_history(
    asset: Optional[str] = None,
    limit: int = 100
):
    """Get trade history"""
    history = await position_tracker.get_trade_history(
        limit=limit,
        asset=asset
    )
    return {"trades": history}


# Analytics endpoints
@router.get("/analytics/summary")
async def get_analytics_summary(
    period: str = Query("week", description="today, week, month, all"),
    asset: Optional[str] = None
):
    """Get analytics summary"""
    now = datetime.utcnow()

    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = None

    summary = await analytics.get_summary(
        start_date=start_date,
        end_date=now,
        asset=asset
    )

    return summary


@router.get("/analytics/by-asset")
async def get_analytics_by_asset(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get analytics breakdown by asset"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    data = await analytics.get_by_asset(start_date=start, end_date=end)
    return {"by_asset": data}


@router.get("/analytics/by-date")
async def get_analytics_by_date(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    asset: Optional[str] = None
):
    """Get analytics breakdown by date"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    data = await analytics.get_by_date(start_date=start, end_date=end, asset=asset)
    return {"by_date": data}


@router.get("/analytics/by-hour")
async def get_analytics_by_hour(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    asset: Optional[str] = None
):
    """Get analytics breakdown by hour of day"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    data = await analytics.get_by_hour(start_date=start, end_date=end, asset=asset)
    return {"by_hour": data}


@router.get("/analytics/profit-distribution")
async def get_profit_distribution(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    asset: Optional[str] = None,
    bin_size: float = 0.5
):
    """Get profit distribution histogram"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    data = await analytics.get_profit_distribution(
        start_date=start,
        end_date=end,
        asset=asset,
        bin_size=bin_size
    )
    return {"distribution": data}


@router.get("/analytics/trade-performance")
async def get_trade_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get trade performance statistics"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    data = await analytics.get_trade_performance(start_date=start, end_date=end)
    return data


@router.get("/analytics/pnl")
async def get_pnl_summary():
    """Get P&L summary"""
    return await position_tracker.get_pnl_summary()


@router.get("/analytics/export")
async def export_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    asset: Optional[str] = None
):
    """Export opportunities to CSV"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    csv_data = await analytics.export_csv(
        start_date=start,
        end_date=end,
        asset=asset
    )

    return PlainTextResponse(
        csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=opportunities.csv"}
    )
