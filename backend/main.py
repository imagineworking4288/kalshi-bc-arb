from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api.routes import router
from .api.websocket import websocket_endpoint
from .api.websocket_routes import router as ws_router
from .database.connection import db
from .config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.initialize()

    settings = get_settings()
    mode = "PAPER" if settings.paper_trading_mode else "LIVE"
    print("=" * 50)
    print("Kalshi Trading Platform")
    print(f"Trading Mode: {mode}")
    print(f"Database: {settings.database_path}")
    print("=" * 50)

    if not settings.paper_trading_mode:
        print("WARNING: Live trading is enabled!")
        print("WARNING: Real money will be used for trades!")

    # Initialize auto-trader
    from .api import routes
    from .services.auto_trader import AutoTrader
    from .services.kalshi_client import KalshiClient

    kalshi_client = KalshiClient()
    routes.auto_trader_instance = AutoTrader(kalshi_client, db)
    await routes.auto_trader_instance.load_config()
    print(f"AutoTrader initialized (mode: {routes.auto_trader_instance._mode_name()})")
    print("=" * 50)

    # Initialize BTC Arbitrage Engine
    try:
        btc_arb_engine = routes.get_btc_arb_engine()
        await btc_arb_engine.start()
        print("[STARTUP] BTC Arbitrage Engine started")
        print("=" * 50)
    except Exception as e:
        print(f"[STARTUP] BTC Arbitrage Engine failed to start: {e}")

    # Initialize Strategy Orchestrator (unified trading engine)
    try:
        from .api.websocket import manager as ws_manager
        from .services.core import (
            StrategyOrchestrator,
            SignalManager,
            KellySizing, KellyConfig,
            RiskManager, RiskLimits,
            CircuitBreaker, CBConfig,
            BatchExecutor,
            PerformanceTracker,
            AlertService
        )

        # Initialize core components
        signals = SignalManager(db)
        kelly = KellySizing(KellyConfig())
        risk = RiskManager(RiskLimits(), db)
        circuit = CircuitBreaker(CBConfig())
        executor = BatchExecutor(kalshi_client)
        performance = PerformanceTracker(db)
        alerts = AlertService(ws_manager)

        # Create orchestrator
        orchestrator = StrategyOrchestrator(
            db=db,
            signals=signals,
            kelly=kelly,
            risk=risk,
            circuit=circuit,
            executor=executor,
            performance=performance,
            alerts=alerts
        )

        # Load saved config
        await orchestrator.load_config()

        # Register with routes
        routes.set_orchestrator(orchestrator)

        print("[STARTUP] Strategy Orchestrator initialized")
        print("=" * 50)
    except Exception as e:
        print(f"[STARTUP] Strategy Orchestrator failed to initialize: {e}")
        import traceback
        traceback.print_exc()

    yield

    # Shutdown
    if routes.auto_trader_instance and routes.auto_trader_instance.is_running:
        await routes.auto_trader_instance.stop()

    # Shutdown BTC arbitrage engine
    try:
        btc_arb_engine = routes.get_btc_arb_engine()
        await btc_arb_engine.stop()
        print("[SHUTDOWN] BTC Arbitrage Engine stopped")
    except Exception as e:
        print(f"[SHUTDOWN] Error stopping BTC arbitrage engine: {e}")

    # Shutdown Strategy Orchestrator
    try:
        orchestrator = routes.get_orchestrator()
        if orchestrator and orchestrator._is_running:
            await orchestrator.stop()
            print("[SHUTDOWN] Strategy Orchestrator stopped")
    except Exception as e:
        print(f"[SHUTDOWN] Error stopping Strategy Orchestrator: {e}")

    print("Shutting down...")


app = FastAPI(
    title="Kalshi Arbitrage Scanner",
    description="Detect and execute arbitrage opportunities on Kalshi",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router, prefix="/api")

# WebSocket routes (advanced features: subscriptions, broadcasts)
app.include_router(ws_router, prefix="/api")

# Legacy WebSocket (backward compatibility)
app.websocket("/ws")(websocket_endpoint)


@app.get("/health")
async def health():
    settings = get_settings()
    return {"status": "healthy", "paper_mode": settings.paper_trading_mode}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
