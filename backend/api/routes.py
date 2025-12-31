from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone

from ..config import get_settings
from ..models.schemas import ExecuteRequest, ResetRequest, TradeRequest, WatchlistAddRequest
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
from ..services.portfolio_service import PortfolioService
from ..services.watchlist_service import WatchlistService

router = APIRouter()

# Services
kalshi = KalshiClient()
spot_client = SpotPriceClient()
classifier = MarketClassifier()
detector = ArbitrageDetector()
executor = TradeExecutor(kalshi)
paper = PaperTradingService()
portfolio_service = PortfolioService()
watchlist_service = WatchlistService()

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


# ============== MANUAL TRADING ==============

@router.post("/trade/place")
async def place_trade(request: TradeRequest):
    """
    Place a manual trade in paper mode, live mode, or both simultaneously.
    """
    import uuid
    from ..database.connection import db
    from ..services.fee_calculator import calculate_fee

    results = []

    for mode in request.modes:
        order_id = str(uuid.uuid4())

        try:
            if mode == "paper":
                # Execute paper trade
                async with db.connection() as conn:
                    # Get paper account balance
                    cursor = await conn.execute("SELECT balance FROM paper_account WHERE id = 1")
                    balance_row = await cursor.fetchone()

                    if not balance_row:
                        results.append({
                            "mode": "paper",
                            "order_id": order_id,
                            "status": "failed",
                            "error": "Paper account not initialized"
                        })
                        continue

                    # Calculate cost
                    price_dollars = request.price_cents / 100
                    total_cost = request.count * price_dollars
                    total_fees = calculate_fee(request.count, price_dollars)
                    total_debit = total_cost + total_fees

                    current_balance = balance_row[0]
                    if current_balance < total_debit:
                        results.append({
                            "mode": "paper",
                            "order_id": order_id,
                            "status": "failed",
                            "error": f"Insufficient balance: ${current_balance:.2f} < ${total_debit:.2f}"
                        })
                        continue

                    # Record order
                    now = datetime.now(timezone.utc).isoformat()
                    await conn.execute(
                        """INSERT INTO manual_orders
                           (id, created_at, ticker, side, action, count, price_cents, mode, status,
                            filled_count, avg_fill_price, total_cost, total_fees, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (order_id, now, request.ticker, request.side, request.action, request.count,
                         request.price_cents, "paper", "filled", request.count, price_dollars,
                         total_cost, total_fees, now)
                    )

                    # Create position
                    position_id = str(uuid.uuid4())
                    await conn.execute(
                        """INSERT INTO paper_positions
                           (id, created_at, ticker, side, contracts, avg_price, total_cost, total_fees,
                            settlement_time, settled, trade_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (position_id, now, request.ticker, request.side, request.count, price_dollars,
                         total_cost, total_fees, datetime.now(timezone.utc).isoformat(), 0, order_id)
                    )

                    # Update balance
                    new_balance = current_balance - total_debit
                    await conn.execute(
                        "UPDATE paper_account SET balance = ?, updated_at = ? WHERE id = 1",
                        (new_balance, now)
                    )

                    await conn.commit()

                    results.append({
                        "mode": "paper",
                        "order_id": order_id,
                        "status": "filled",
                        "filled_count": request.count,
                        "avg_fill_price": price_dollars,
                        "total_cost": total_cost,
                        "total_fees": total_fees
                    })

            elif mode == "live":
                # Execute live trade via Kalshi API
                try:
                    kalshi_result = await kalshi.place_order(
                        ticker=request.ticker,
                        side=request.side,
                        action=request.action,
                        count=request.count,
                        price=request.price_cents
                    )

                    # Parse Kalshi response
                    order = kalshi_result.get("order", {})
                    kalshi_order_id = order.get("order_id")
                    filled_count = order.get("filled_count", 0)
                    status_map = {"resting": "pending", "filled": "filled", "canceled": "cancelled"}
                    status = status_map.get(order.get("status", "pending"), "pending")

                    # Calculate actuals
                    fill_price = order.get("yes_price", request.price_cents) / 100
                    actual_cost = filled_count * fill_price
                    actual_fees = order.get("total_fee", 0) / 100

                    # Record order
                    async with db.connection() as conn:
                        now = datetime.now(timezone.utc).isoformat()
                        await conn.execute(
                            """INSERT INTO manual_orders
                               (id, created_at, ticker, side, action, count, price_cents, mode, status,
                                filled_count, avg_fill_price, total_cost, total_fees, kalshi_order_id, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (order_id, now, request.ticker, request.side, request.action, request.count,
                             request.price_cents, "live", status, filled_count, fill_price,
                             actual_cost, actual_fees, kalshi_order_id, now)
                        )
                        await conn.commit()

                    results.append({
                        "mode": "live",
                        "order_id": order_id,
                        "kalshi_order_id": kalshi_order_id,
                        "status": status,
                        "filled_count": filled_count,
                        "avg_fill_price": fill_price,
                        "total_cost": actual_cost,
                        "total_fees": actual_fees
                    })

                except Exception as e:
                    # Record failed live order
                    async with db.connection() as conn:
                        now = datetime.now(timezone.utc).isoformat()
                        await conn.execute(
                            """INSERT INTO manual_orders
                               (id, created_at, ticker, side, action, count, price_cents, mode, status, error, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (order_id, now, request.ticker, request.side, request.action, request.count,
                             request.price_cents, "live", "failed", str(e), now)
                        )
                        await conn.commit()

                    results.append({
                        "mode": "live",
                        "order_id": order_id,
                        "status": "failed",
                        "error": str(e)
                    })

        except Exception as e:
            results.append({
                "mode": mode,
                "order_id": order_id,
                "status": "failed",
                "error": str(e)
            })

    success = all(r["status"] in ["filled", "pending"] for r in results)
    message = f"Placed {len([r for r in results if r['status'] in ['filled', 'pending']])} of {len(results)} orders"

    return {
        "results": results,
        "success": success,
        "message": message
    }


@router.get("/trade/market/{ticker}")
async def get_market_details(ticker: str):
    """Fetch full market details from Kalshi API."""
    try:
        market = await kalshi.get_market(ticker)
        if not market:
            raise HTTPException(404, f"Market {ticker} not found")

        return {
            "ticker": market.get("ticker"),
            "title": market.get("title"),
            "subtitle": market.get("subtitle"),
            "status": market.get("status"),
            "yes_ask": market.get("yes_ask"),
            "no_ask": market.get("no_ask"),
            "yes_bid": market.get("yes_bid"),
            "no_bid": market.get("no_bid"),
            "volume": market.get("volume", 0),
            "open_interest": market.get("open_interest", 0),
            "close_time": market.get("close_time"),
            "expiration_time": market.get("expiration_time")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch market: {str(e)}")


# ============== PORTFOLIO ==============

@router.get("/portfolio/summary")
async def get_portfolio_summary():
    """Get portfolio summary across paper and live modes."""
    return await portfolio_service.get_summary()


@router.get("/portfolio/positions")
async def get_portfolio_positions():
    """Get all positions from paper and live modes."""
    positions = await portfolio_service.get_all_positions()
    return {"positions": positions}


@router.get("/portfolio/orders")
async def get_portfolio_orders(mode: Optional[str] = None, limit: int = 50):
    """Get manual order history."""
    orders = await portfolio_service.get_orders(mode, limit)
    return {"orders": orders}


# ============== WATCHLIST ==============

@router.get("/watchlist")
async def get_watchlist():
    """Get all watchlist items with fresh prices."""
    items = await watchlist_service.get_all()
    return {"items": items}


@router.post("/watchlist")
async def add_to_watchlist(request: WatchlistAddRequest):
    """Add market to watchlist."""
    result = await watchlist_service.add(request.ticker, request.notes)
    return result


@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str):
    """Remove market from watchlist."""
    success = await watchlist_service.remove(ticker)
    if not success:
        raise HTTPException(404, f"Market {ticker} not in watchlist")
    return {"message": f"Removed {ticker} from watchlist"}
