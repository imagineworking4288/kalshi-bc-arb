from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional
from datetime import datetime, timezone

from ..config import get_settings
from ..database.connection import db
from ..models.schemas import ExecuteRequest, ResetRequest, TradeRequest, WatchlistAddRequest
from ..services.kalshi_client import KalshiClient
from ..services.spot_price_client import SpotPriceClient
from ..services.market_classifier import (
    MarketClassifier,
    MarketType,
    ThresholdMarket,
    BracketMarket,
    MarketGroup
)
from ..services.arbitrage_detector import ArbitrageDetector
from ..services.trade_executor import TradeExecutor
from ..services.paper_trading import PaperTradingService
from ..services.portfolio_service import PortfolioService
from ..services.watchlist_service import WatchlistService
from ..services.scanner_db import ScannerDatabase
from ..services.log_config import LOG_DIR, MAIN_LOG

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
scanner_db = ScannerDatabase()

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


# ============== AUTO-TRADER ==============

# Auto-trader instance (initialized on startup)
auto_trader_instance = None


@router.get("/auto-trader/status")
async def get_auto_trader_status():
    """Get current auto-trader status and configuration."""
    if not auto_trader_instance:
        return {"enabled": 0, "mode": "NOT INITIALIZED", "is_running": False}
    return await auto_trader_instance.get_status()


@router.post("/auto-trader/config")
async def update_auto_trader_config(request: dict):
    """Update auto-trader configuration."""
    if not auto_trader_instance:
        raise HTTPException(500, "Auto-trader not initialized")

    return await auto_trader_instance.update_config(**request)


@router.post("/auto-trader/start")
async def start_auto_trader():
    """Start the auto-trader."""
    if not auto_trader_instance:
        raise HTTPException(500, "Auto-trader not initialized")

    await auto_trader_instance.start()
    return {"success": True, "status": await auto_trader_instance.get_status()}


@router.post("/auto-trader/stop")
async def stop_auto_trader():
    """Stop the auto-trader."""
    if not auto_trader_instance:
        raise HTTPException(500, "Auto-trader not initialized")

    await auto_trader_instance.stop()
    return {"success": True, "status": await auto_trader_instance.get_status()}


@router.get("/auto-trader/scan")
async def manual_scan():
    """Manually trigger edge scan without executing trades."""
    if not auto_trader_instance:
        raise HTTPException(500, "Auto-trader not initialized")

    signals = await auto_trader_instance.manual_scan()
    return {"signals": signals, "count": len(signals)}


@router.get("/auto-trader/signals")
async def get_signals(status: Optional[str] = None, limit: int = 50):
    """Get trading signals from database."""
    query = "SELECT * FROM trading_signals"
    params = []

    if status:
        query += " WHERE status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    async with db.connection() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return {"signals": [dict(zip(columns, row)) for row in rows]}


# ===========================================
# BTC ARBITRAGE ENGINE (Singleton)
# ===========================================
btc_arb_engine_instance: Optional['BTCArbitrageEngine'] = None

def get_btc_arb_engine():
    global btc_arb_engine_instance
    if btc_arb_engine_instance is None:
        from ..services.btc_arb_engine import BTCArbitrageEngine
        kalshi = KalshiClient()
        btc_arb_engine_instance = BTCArbitrageEngine(kalshi, db)
    return btc_arb_engine_instance


# ===========================================
# BTC ARBITRAGE ENDPOINTS
# ===========================================

@router.get("/btc-arb/status")
async def get_btc_arb_status():
    """Get BTC arbitrage engine full status including market data and calculations."""
    engine = get_btc_arb_engine()
    return await engine.get_full_status()


@router.put("/btc-arb/config")
async def update_btc_arb_config(request: Request):
    """Update BTC arbitrage engine configuration."""
    data = await request.json()
    engine = get_btc_arb_engine()
    return await engine.update_config(**data)


@router.post("/btc-arb/execute/{opportunity_id}")
async def execute_btc_arb(opportunity_id: str):
    """Manually execute a BTC arbitrage opportunity."""
    engine = get_btc_arb_engine()
    return await engine.manual_execute(opportunity_id)


@router.post("/btc-arb/start")
async def start_btc_arb_engine():
    """Start the BTC arbitrage engine."""
    engine = get_btc_arb_engine()
    await engine.start()
    return await engine.get_status()


@router.post("/btc-arb/stop")
async def stop_btc_arb_engine():
    """Stop the BTC arbitrage engine."""
    engine = get_btc_arb_engine()
    await engine.stop()
    return await engine.get_status()


@router.get("/btc-arb/executions")
async def get_btc_arb_executions(limit: int = 50):
    """Get BTC arbitrage execution history."""
    async with db.connection() as conn:
        cursor = await conn.execute("""
            SELECT * FROM btc_arb_executions
            ORDER BY executed_at DESC LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return {'executions': [dict(zip(columns, row)) for row in rows]}


@router.get("/btc-arb/raw-markets")
async def get_raw_btc_markets():
    """Diagnostic: Get raw market data from KXBTC and KXBTCD series."""
    kxbtc_markets = await kalshi.get_markets(series_ticker="KXBTC", status="open")
    kxbtcd_markets = await kalshi.get_markets(series_ticker="KXBTCD", status="open")

    if isinstance(kxbtc_markets, dict):
        kxbtc_markets = kxbtc_markets.get('markets', [])
    if isinstance(kxbtcd_markets, dict):
        kxbtcd_markets = kxbtcd_markets.get('markets', [])

    # Get sample of each with key fields
    def simplify(m):
        return {
            'ticker': m.get('ticker'),
            'title': m.get('title'),
            'subtitle': m.get('subtitle'),
            'yes_bid': m.get('yes_bid'),
            'yes_ask': m.get('yes_ask'),
            'status': m.get('status')
        }

    return {
        'kxbtc': {
            'total': len(kxbtc_markets),
            'sample': [simplify(m) for m in kxbtc_markets[:10]]
        },
        'kxbtcd': {
            'total': len(kxbtcd_markets),
            'sample': [simplify(m) for m in kxbtcd_markets[:10]]
        },
        'all_kxbtc_tickers': [m.get('ticker') for m in kxbtc_markets[:30]],
        'all_kxbtcd_tickers': [m.get('ticker') for m in kxbtcd_markets[:30]]
    }


@router.get("/btc-arb/ticker-patterns")
async def get_ticker_patterns():
    """Analyze ticker patterns in BTC markets."""
    kxbtc = await kalshi.get_markets(series_ticker="KXBTC", status="open")
    kxbtcd = await kalshi.get_markets(series_ticker="KXBTCD", status="open")

    if isinstance(kxbtc, dict):
        kxbtc = kxbtc.get('markets', [])
    if isinstance(kxbtcd, dict):
        kxbtcd = kxbtcd.get('markets', [])

    # Categorize by pattern
    kxbtc_patterns = {'B_tickers': [], 'T_tickers': [], 'other': []}
    for m in kxbtc:
        ticker = m.get('ticker', '')
        if '-B' in ticker:
            kxbtc_patterns['B_tickers'].append(ticker)
        elif '-T' in ticker:
            kxbtc_patterns['T_tickers'].append(ticker)
        else:
            kxbtc_patterns['other'].append(ticker)

    kxbtcd_patterns = {'B_tickers': [], 'T_tickers': [], 'other': []}
    for m in kxbtcd:
        ticker = m.get('ticker', '')
        if '-B' in ticker:
            kxbtcd_patterns['B_tickers'].append(ticker)
        elif '-T' in ticker:
            kxbtcd_patterns['T_tickers'].append(ticker)
        else:
            kxbtcd_patterns['other'].append(ticker)

    return {
        'kxbtc': {
            'total': len(kxbtc),
            'B_count': len(kxbtc_patterns['B_tickers']),
            'T_count': len(kxbtc_patterns['T_tickers']),
            'other_count': len(kxbtc_patterns['other']),
            'sample_B': kxbtc_patterns['B_tickers'][:5],
            'sample_T': kxbtc_patterns['T_tickers'][:5]
        },
        'kxbtcd': {
            'total': len(kxbtcd),
            'B_count': len(kxbtcd_patterns['B_tickers']),
            'T_count': len(kxbtcd_patterns['T_tickers']),
            'other_count': len(kxbtcd_patterns['other']),
            'sample_B': kxbtcd_patterns['B_tickers'][:5],
            'sample_T': kxbtcd_patterns['T_tickers'][:5]
        }
    }


@router.get("/btc-arb/debug")
async def get_btc_arb_debug():
    """
    Debug endpoint: Shows detailed diagnostic info about the arbitrage scanner.

    Returns:
    - Markets from each series (KXBTC, KXBTCD)
    - Settlement times found for ranges and thresholds
    - Common settlement times (where arbitrage can exist)
    - Sample calculations showing why opportunities were/weren't found
    """
    from collections import defaultdict

    # Fetch from both series using events API (same as scanner)
    all_markets = []
    series_stats = {}

    for series in ["KXBTC", "KXBTCD"]:
        try:
            events = await kalshi.get_events(
                series_ticker=series,
                status="open",
                with_nested_markets=True,
                limit=100
            )

            series_markets = []
            for event in events:
                for market in event.get("markets", []):
                    market["_series"] = series
                    market["_expiration"] = market.get("expiration_time") or market.get("close_time")
                    series_markets.append(market)

            all_markets.extend(series_markets)
            series_stats[series] = {
                'events': len(events),
                'total_markets': len(series_markets),
                'ranges': len([m for m in series_markets if '-B' in m.get('ticker', '')]),
                'thresholds': len([m for m in series_markets if '-T' in m.get('ticker', '')])
            }
        except Exception as e:
            series_stats[series] = {'error': str(e)}

    # Separate by type
    range_markets = [m for m in all_markets if '-B' in m.get('ticker', '')]
    threshold_markets = [m for m in all_markets if '-T' in m.get('ticker', '')]

    # Group by settlement time
    def group_by_settlement(markets):
        groups = defaultdict(list)
        for m in markets:
            exp = m.get('_expiration', '')[:16] if m.get('_expiration') else ''
            if exp:
                groups[exp].append(m.get('ticker'))
        return dict(groups)

    range_settlements = group_by_settlement(range_markets)
    threshold_settlements = group_by_settlement(threshold_markets)

    # Find common
    common = set(range_settlements.keys()) & set(threshold_settlements.keys())

    # Sample calculation for first common settlement
    sample_calc = None
    if common:
        first_settlement = sorted(common)[0]
        first_range = [m for m in range_markets if (m.get('_expiration') or '')[:16] == first_settlement]
        first_thresh = [m for m in threshold_markets if (m.get('_expiration') or '')[:16] == first_settlement]

        if first_range and first_thresh:
            r = first_range[0]
            floor = r.get('floor_strike')
            cap = r.get('cap_strike')

            # Find matching thresholds
            lower_t = None
            upper_t = None
            for t in first_thresh:
                strike = t.get('floor_strike')
                if strike is not None:
                    if abs(strike - floor) < 1 or abs(strike - (floor - 0.01)) < 1:
                        lower_t = t
                    if abs(strike - (cap + 0.01)) < 1 or abs(strike - round(cap + 1)) < 1:
                        upper_t = t

            sample_calc = {
                'settlement': first_settlement,
                'range': {
                    'ticker': r.get('ticker'),
                    'floor_strike': floor,
                    'cap_strike': cap,
                    'yes_ask': r.get('yes_ask')
                },
                'lower_threshold': {
                    'ticker': lower_t.get('ticker') if lower_t else None,
                    'floor_strike': lower_t.get('floor_strike') if lower_t else None,
                    'yes_bid': lower_t.get('yes_bid') if lower_t else None,
                    'no_cost': 100 - lower_t.get('yes_bid') if lower_t and lower_t.get('yes_bid') else None
                } if lower_t else 'NOT FOUND',
                'upper_threshold': {
                    'ticker': upper_t.get('ticker') if upper_t else None,
                    'floor_strike': upper_t.get('floor_strike') if upper_t else None,
                    'yes_ask': upper_t.get('yes_ask') if upper_t else None
                } if upper_t else 'NOT FOUND'
            }

            # Calculate total if we have all prices
            if lower_t and upper_t:
                range_ask = r.get('yes_ask')
                lower_bid = lower_t.get('yes_bid')
                upper_ask = upper_t.get('yes_ask')
                if all([range_ask, lower_bid, upper_ask]):
                    total = range_ask + (100 - lower_bid) + upper_ask
                    sample_calc['total_cost_cents'] = total
                    sample_calc['edge_cents'] = 100 - total
                    sample_calc['is_profitable'] = total < 100

    return {
        'series_stats': series_stats,
        'totals': {
            'ranges': len(range_markets),
            'thresholds': len(threshold_markets)
        },
        'settlement_times': {
            'range_count': len(range_settlements),
            'threshold_count': len(threshold_settlements),
            'common_count': len(common),
            'common_times': sorted(list(common))[:10],
            'sample_range_times': sorted(list(range_settlements.keys()))[:5],
            'sample_threshold_times': sorted(list(threshold_settlements.keys()))[:5]
        },
        'sample_calculation': sample_calc,
        'diagnosis': {
            'has_ranges': len(range_markets) > 0,
            'has_thresholds': len(threshold_markets) > 0,
            'has_common_settlements': len(common) > 0,
            'issue': (
                'No ranges found' if not range_markets else
                'No thresholds found' if not threshold_markets else
                'No common settlement times - ranges and thresholds expire at different times' if not common else
                'OK - common settlements found, check calculations'
            )
        }
    }


# ============== WEATHER ARBITRAGE ROUTES ==============

@router.get("/weather-arb/status")
async def get_weather_arb_status():
    """Get weather arbitrage scanner status from database."""
    result = scanner_db.get_scanner_result("weather")
    if result:
        return result
    return {"error": "Scanner not running", "hint": "Start scanner service"}


@router.get("/weather-arb/city/{code}")
async def get_weather_city(code: str):
    """Get weather status for a specific city."""
    result = scanner_db.get_scanner_result("weather")
    if not result:
        return {"error": "Scanner not running"}

    cities = result.get("cities", {})
    city = cities.get(code.upper())
    if city:
        return city
    return {"error": f"City {code} not found"}


@router.get("/weather-arb/history")
async def get_weather_arb_history(limit: int = 100):
    """Get weather scanner history."""
    return scanner_db.get_scanner_history("weather", limit)


# ============== UNIFIED SCANNER ROUTES ==============

@router.get("/scanners/status")
async def get_all_scanners_status():
    """Get status of all scanners."""
    return scanner_db.get_all_results()


# ============== LOG ROUTES ==============

@router.get("/logs/recent")
async def get_recent_logs(lines: int = 100, source: str = None, level: str = None):
    """Get recent log entries."""
    try:
        if not MAIN_LOG.exists():
            return {"logs": [], "error": "No log file yet"}

        with open(MAIN_LOG, 'r') as f:
            all_lines = f.readlines()

        recent = all_lines[-lines:] if len(all_lines) > lines else all_lines

        if source:
            recent = [l for l in recent if source.lower() in l.lower()]
        if level:
            recent = [l for l in recent if f'| {level.upper()} |' in l]

        return {"logs": [l.strip() for l in recent], "total": len(all_lines)}
    except Exception as e:
        return {"logs": [], "error": str(e)}


@router.get("/logs/files")
async def get_log_files():
    """List available log files."""
    files = []
    for f in LOG_DIR.glob("*.log"):
        stat = f.stat()
        files.append({
            "name": f.name,
            "size": f"{stat.st_size / 1024:.1f} KB",
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    return {"files": files}


# ===========================================
# ORCHESTRATOR (Unified Trading Engine)
# ===========================================

# Orchestrator instance (initialized on startup in main.py lifespan)
orchestrator_instance = None


def get_orchestrator():
    """Get the orchestrator instance."""
    global orchestrator_instance
    return orchestrator_instance


def set_orchestrator(instance):
    """Set the orchestrator instance (called from main.py lifespan)."""
    global orchestrator_instance
    orchestrator_instance = instance


@router.get("/orchestrator/status")
async def get_orchestrator_status():
    """Get orchestrator status including all strategies and components."""
    orch = get_orchestrator()
    if not orch:
        return {"is_running": False, "error": "Orchestrator not initialized"}
    return orch.get_status()


@router.post("/orchestrator/start")
async def start_orchestrator():
    """Start the orchestrator and all enabled strategies."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    await orch.start()
    return {"success": True, "status": orch.get_status()}


@router.post("/orchestrator/stop")
async def stop_orchestrator():
    """Stop the orchestrator and all running strategies."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    await orch.stop()
    return {"success": True, "status": orch.get_status()}


@router.post("/orchestrator/auto-trade")
async def set_orchestrator_auto_trade(enabled: bool = True):
    """Enable or disable auto-trading."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    orch.set_auto_trade(enabled)
    return {"success": True, "auto_trade_enabled": enabled}


@router.post("/orchestrator/mode")
async def set_orchestrator_mode(mode: str = "paper"):
    """Set trading mode (paper or live)."""
    if mode not in ("paper", "live"):
        raise HTTPException(400, "Mode must be 'paper' or 'live'")
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    orch.set_mode(mode)
    return {"success": True, "mode": mode}


@router.post("/orchestrator/strategy/{strategy_type}/enable")
async def enable_strategy(strategy_type: str, enabled: bool = True):
    """Enable or disable a specific strategy."""
    from ..services.core import StrategyType
    try:
        st = StrategyType(strategy_type)
    except ValueError:
        raise HTTPException(400, f"Unknown strategy type: {strategy_type}")

    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")

    success = orch.enable_strategy(st, enabled)
    if not success:
        raise HTTPException(404, f"Strategy {strategy_type} not registered")
    return {"success": True, "strategy": strategy_type, "enabled": enabled}


@router.post("/orchestrator/scan")
async def trigger_manual_scan(strategy_type: Optional[str] = None):
    """Manually trigger a scan for signals."""
    from ..services.core import StrategyType

    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")

    st = None
    if strategy_type:
        try:
            st = StrategyType(strategy_type)
        except ValueError:
            raise HTTPException(400, f"Unknown strategy type: {strategy_type}")

    signals = await orch.manual_scan(st)
    return {"signals": signals, "count": len(signals)}


@router.post("/orchestrator/execute/{signal_id}")
async def execute_signal(signal_id: str):
    """Manually execute a specific signal."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")

    result = await orch.manual_execute(signal_id)
    return result


@router.post("/orchestrator/config")
async def save_orchestrator_config():
    """Save current orchestrator configuration to database."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    await orch.save_config()
    return {"success": True}


# ===========================================
# SIGNALS V2 (Unified Signal Management)
# ===========================================

@router.get("/signals")
async def get_signals_v2(
    strategy_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """Get signals from the unified signals table."""
    from ..services.core import StrategyType, SignalStatus

    orch = get_orchestrator()
    if not orch:
        # Fallback to direct DB query
        query = "SELECT * FROM signals_v2 WHERE 1=1"
        params = []

        if strategy_type:
            query += " AND strategy_type = ?"
            params.append(strategy_type)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with db.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            columns = [d[0] for d in cursor.description]
            return {"signals": [dict(zip(columns, row)) for row in rows]}

    # Use signal manager
    st = None
    if strategy_type:
        try:
            st = StrategyType(strategy_type)
        except ValueError:
            pass

    ss = None
    if status:
        try:
            ss = SignalStatus(status)
        except ValueError:
            pass

    signals = await orch.signals.get_history(st, ss, limit)
    return {"signals": [s.to_dict() for s in signals]}


@router.get("/signals/stats")
async def get_signal_stats(days: int = 7):
    """Get signal statistics."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    return await orch.signals.get_stats(days)


# ===========================================
# PERFORMANCE TRACKING
# ===========================================

@router.get("/performance/metrics")
async def get_performance_metrics(days: int = 30):
    """Get performance metrics."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    metrics = await orch.performance.get_metrics(days)
    return metrics.to_dict()


@router.get("/performance/daily")
async def get_daily_pnl(days: int = 30):
    """Get daily P&L history."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    return await orch.performance.get_daily_pnl(days)


@router.get("/performance/trades")
async def get_trade_history(
    strategy_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """Get trade history."""
    orch = get_orchestrator()
    if not orch:
        # Direct DB query fallback
        query = "SELECT * FROM trade_records WHERE 1=1"
        params = []

        if strategy_type:
            query += " AND strategy_type = ?"
            params.append(strategy_type)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY entry_time DESC LIMIT ?"
        params.append(limit)

        async with db.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            columns = [d[0] for d in cursor.description]
            return {"trades": [dict(zip(columns, row)) for row in rows]}

    return await orch.performance.get_trades(strategy_type, status, limit)


# ===========================================
# CIRCUIT BREAKER
# ===========================================

@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status():
    """Get circuit breaker status."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    return orch.circuit.get_status()


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker():
    """Reset the circuit breaker."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    await orch.circuit.reset()
    return {"success": True, "status": orch.circuit.get_status()}


@router.post("/circuit-breaker/trip")
async def trip_circuit_breaker(reason: str = "Manual trip"):
    """Manually trip the circuit breaker."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    await orch.circuit.force_trip(reason)
    return {"success": True, "status": orch.circuit.get_status()}


# ===========================================
# RISK MANAGER
# ===========================================

@router.get("/risk/status")
async def get_risk_status():
    """Get risk manager status."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    return orch.risk.get_status()


@router.post("/risk/sync")
async def sync_risk_positions():
    """Sync risk manager positions with Kalshi."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    # Get live positions from executor
    positions = await kalshi.get_portfolio_positions()
    await orch.risk.sync_positions(positions)
    return {"success": True, "status": orch.risk.get_status()}


# ===========================================
# ALERTS
# ===========================================

@router.get("/alerts")
async def get_alerts(limit: int = 20):
    """Get recent alerts."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    return {"alerts": orch.alerts.get_recent(limit)}


@router.get("/alerts/unacknowledged")
async def get_unacknowledged_alerts(limit: int = 50):
    """Get unacknowledged alerts."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    return {"alerts": orch.alerts.get_unacknowledged(limit)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    success = orch.alerts.acknowledge(alert_id)
    if not success:
        raise HTTPException(404, f"Alert {alert_id} not found")
    return {"success": True}


@router.post("/alerts/acknowledge-all")
async def acknowledge_all_alerts():
    """Acknowledge all alerts."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    count = orch.alerts.acknowledge_all()
    return {"success": True, "acknowledged": count}


@router.get("/alerts/stats")
async def get_alert_stats():
    """Get alert statistics."""
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")
    return orch.alerts.get_stats()


# ===========================================
# BACKTESTING
# ===========================================

@router.post("/backtest/run")
async def run_backtest(request: Request):
    """Run a backtest on historical data."""
    from ..services.core import BacktestConfig, BacktestEngine
    from datetime import datetime

    data = await request.json()

    # Parse config
    config = BacktestConfig(
        start_date=datetime.fromisoformat(data.get("start_date")),
        end_date=datetime.fromisoformat(data.get("end_date")),
        initial_balance_cents=data.get("initial_balance_cents", 100000),
        kelly_fraction=data.get("kelly_fraction", 0.25),
        min_edge_percent=data.get("min_edge_percent", 5.0),
        max_position_per_trade=data.get("max_position_per_trade", 100)
    )

    orch = get_orchestrator()
    if not orch:
        raise HTTPException(500, "Orchestrator not initialized")

    engine = BacktestEngine(db)

    # Get strategy if specified
    strategy_type = data.get("strategy_type")
    if strategy_type:
        from ..services.core import StrategyType
        try:
            st = StrategyType(strategy_type)
            strategy = orch._strategies.get(st)
            if not strategy:
                raise HTTPException(404, f"Strategy {strategy_type} not registered")
            result = await engine.run(strategy, config)
            return result.to_dict()
        except ValueError:
            raise HTTPException(400, f"Unknown strategy type: {strategy_type}")
    else:
        # Run all strategies
        results = await engine.run_multiple(list(orch._strategies.values()), config)
        return {st: r.to_dict() for st, r in results.items()}
