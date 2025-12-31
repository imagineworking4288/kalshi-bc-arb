from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone

from ..config import get_settings
from ..models.schemas import ExecuteRequest, ResetRequest
from ..services import (
    KalshiClient,
    SpotPriceClient,
    MarketClassifier,
    MarketType,
    ThresholdMarket,
    BracketMarket,
    MarketGroup,
    ArbitrageDetector,
    TradeExecutor,
    PaperTradingService
)

router = APIRouter()

# Services
kalshi = KalshiClient()
spot_client = SpotPriceClient()
classifier = MarketClassifier()
detector = ArbitrageDetector()
executor = TradeExecutor(kalshi)
paper = PaperTradingService()

# Cache for opportunities
_opp_cache: dict = {}


# ============== CONFIG ==============

@router.get("/config")
async def get_config():
    settings = get_settings()
    return {
        "paper_mode": settings.paper_trading_mode,
        "api_configured": settings.has_kalshi_credentials,
        "paper_starting_balance": settings.paper_starting_balance
    }


# ============== MARKET DATA ==============

@router.get("/spot-price")
async def get_spot_price():
    price = await spot_client.get_price("BTC")
    if price:
        return {
            "asset": price.asset,
            "price": price.price,
            "timestamp": price.timestamp.isoformat(),
            "source": price.source
        }
    raise HTTPException(503, "Spot price unavailable")


@router.get("/opportunities")
async def get_opportunities(
    min_profit: float = Query(1.0, description="Minimum net profit %")
):
    global _opp_cache

    # Fetch BTC events with nested markets (KXBTC = bracket ranges, KXBTCD = daily price)
    all_markets = []
    try:
        for series in ["KXBTC", "KXBTCD"]:
            events = await kalshi.get_events(
                series_ticker=series,
                status="open",
                with_nested_markets=True,
                limit=10
            )

            # Extract nested markets from each event
            for event in events:
                markets = event.get("markets", [])
                settlement_str = event.get("strike_date") or event.get("close_time")
                mutually_exclusive = event.get("mutually_exclusive", False)

                # Add event metadata to each market
                for market in markets:
                    market["_event_settlement"] = settlement_str
                    market["_mutually_exclusive"] = mutually_exclusive
                    all_markets.append(market)
    except Exception as e:
        raise HTTPException(503, f"Failed to fetch events: {e}")

    # Classify and group
    groups: dict[str, MarketGroup] = {}

    for market in all_markets:
        market_type, data = classifier.classify(market)
        if not market_type:
            continue

        # Use event settlement time if available, fallback to market close_time
        settlement_str = market.get("_event_settlement") or market.get("close_time") or market.get("expiration_time")
        if not settlement_str:
            continue

        try:
            settlement = datetime.fromisoformat(settlement_str.replace("Z", "+00:00"))
        except:
            continue

        # Skip expired
        if settlement < datetime.now(timezone.utc):
            continue

        # Only use mutually exclusive events for bracket arbitrage
        if market_type == MarketType.BRACKET and not market.get("_mutually_exclusive", False):
            continue

        group_key = f"BTC_{settlement.isoformat()}"
        if group_key not in groups:
            groups[group_key] = MarketGroup(asset="BTC", settlement_time=settlement)

        # Use yes_ask from market data (already in cents)
        yes_ask_cents = market.get("yes_ask", 50)
        yes_price = yes_ask_cents / 100
        yes_ask = yes_price

        if market_type == MarketType.THRESHOLD:
            groups[group_key].thresholds.append(ThresholdMarket(
                ticker=market["ticker"],
                title=market.get("title", ""),
                asset="BTC",
                strike=data["strike"],
                direction=data["direction"],
                yes_price=yes_price,
                yes_ask=yes_ask,
                volume=market.get("volume", 0),
                settlement_time=settlement
            ))
        elif market_type == MarketType.BRACKET:
            groups[group_key].brackets.append(BracketMarket(
                ticker=market["ticker"],
                title=market.get("title", ""),
                asset="BTC",
                low_bound=data["low_bound"],
                high_bound=data["high_bound"],
                yes_price=yes_price,
                yes_ask=yes_ask,
                volume=market.get("volume", 0),
                settlement_time=settlement
            ))

    # Add spot price
    spot = await spot_client.get_price("BTC")
    for group in groups.values():
        group.spot_price = spot.price if spot else None

    # Find opportunities
    detector.min_profit_pct = min_profit
    opportunities = detector.find_opportunities(list(groups.values()))

    # Cache
    _opp_cache = {opp.id: opp for opp in opportunities}

    return {
        "opportunities": [
            {
                "id": o.id,
                "asset": o.asset,
                "settlement_time": o.settlement_time.isoformat(),
                "threshold_ticker": o.threshold.ticker,
                "threshold_title": o.threshold.title,
                "threshold_strike": o.threshold.strike,
                "bracket_count": len(o.brackets),
                "cost_per_set": o.cost_per_set,
                "fees_per_set": o.fees_per_set,
                "profit_per_set": o.profit_per_set,
                "net_profit_pct": o.net_profit_pct,
                "max_contracts": o.max_contracts,
                "max_liquidity_usd": o.max_liquidity_usd,
                "spot_price": o.spot_price,
                "brackets": [
                    {"ticker": b.ticker, "low": b.low_bound, "high": b.high_bound, "yes_price": b.yes_price}
                    for b in o.brackets
                ]
            }
            for o in opportunities
        ],
        "count": len(opportunities),
        "paper_mode": get_settings().paper_trading_mode
    }


# ============== TRADING ==============

@router.get("/balance")
async def get_balance():
    return await executor.get_balance()


@router.get("/positions")
async def get_positions():
    positions = await executor.get_positions()
    return {"positions": positions, "paper_mode": get_settings().paper_trading_mode}


@router.post("/execute")
async def execute_arbitrage(request: ExecuteRequest):
    opp = _opp_cache.get(request.opportunity_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found. Refresh opportunities list.")

    result = await executor.execute_arbitrage(opp, request.num_contracts)

    return {
        "trade_id": result.trade_id,
        "status": result.status,
        "total_cost": result.total_cost,
        "total_fees": result.total_fees,
        "expected_payout": result.expected_payout,
        "expected_profit": result.expected_profit,
        "expected_profit_pct": getattr(result, 'expected_profit_pct', 0),
        "message": result.message,
        "paper_mode": result.paper_mode,
        "orders": [
            {"ticker": o.ticker, "contracts": o.contracts, "price": o.fill_price, "fee": o.fee}
            if hasattr(o, 'ticker') else o
            for o in result.orders
        ]
    }


# ============== PAPER TRADING ==============

@router.post("/paper/reset")
async def reset_paper(request: ResetRequest = None):
    starting = request.starting_balance if request else None
    return await paper.reset_account(starting)


@router.get("/paper/summary")
async def paper_summary():
    return await paper.get_pnl_summary()


@router.get("/paper/trades")
async def paper_trades(limit: int = 50):
    trades = await paper.get_trades(limit)
    return {"trades": trades}


@router.post("/paper/settle/{position_id}")
async def settle_position(position_id: str, won: bool = True):
    return await paper.settle_position(position_id, won)
