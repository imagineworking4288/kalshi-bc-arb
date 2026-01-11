from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .api.routes import router
from .api.websocket import websocket_endpoint
from .api.websocket_routes import router as ws_router
from .api.prediction_routes import router as prediction_router
from .database.connection import db
from .config import get_settings
from .services.core.execution_gateway import ExecutionGateway
from .services.core.fee_calculator import FeeCalculator
from .services.paper_trading import PaperTradingService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.initialize()

    settings = get_settings()
    mode = "PAPER" if settings.paper_trading_mode else "LIVE"
    print("=" * 50)
    print("  Kalshi Trading Platform")
    print("=" * 50)
    print(f"  Mode: {mode}")
    print(f"  API Configured: {settings.has_kalshi_credentials}")
    print(f"  Database: {settings.database_path}")
    print("=" * 50)

    if not settings.paper_trading_mode:
        print("  WARNING: Live trading is enabled!")
        print("  WARNING: Real money will be used for trades!")

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
            PerformanceTracker,
            AlertService
        )

        # Initialize core components
        signals = SignalManager(db)
        kelly = KellySizing(KellyConfig())
        risk = RiskManager(RiskLimits(), db)
        circuit = CircuitBreaker(CBConfig())
        performance = PerformanceTracker(db)
        alerts = AlertService(ws_manager)

        # Initialize consolidated fee calculator
        fee_calculator = FeeCalculator()
        logger.info("Fee calculator initialized")

        # Initialize paper trading service
        paper_service = PaperTradingService()
        logger.info("Paper trading service initialized")

        # Initialize ExecutionGateway - SINGLE ENTRY POINT FOR ALL TRADES
        gateway = ExecutionGateway(
            kalshi_client=kalshi_client,
            paper_service=paper_service,
            risk_manager=risk,
            circuit_breaker=circuit,
            fee_calculator=fee_calculator,
            db=db,
            alert_service=alerts
        )
        logger.info("ExecutionGateway initialized")

        # Inject gateway into dependent services
        routes.auto_trader_instance.gateway = gateway
        btc_arb_engine.gateway = gateway
        logger.info("Gateway injected into AutoTrader and BTC Arbitrage Engine")

        # Store gateway in app state for route access
        app.state.gateway = gateway
        app.state.fee_calculator = fee_calculator

        # Create orchestrator - uses gateway for execution
        orchestrator = StrategyOrchestrator(
            db=db,
            signals=signals,
            kelly=kelly,
            risk=risk,
            circuit=circuit,
            executor=gateway,  # Use gateway instead of BatchExecutor
            performance=performance,
            alerts=alerts
        )

        # Load saved config
        await orchestrator.load_config()

        # Register with routes
        routes.set_orchestrator(orchestrator)

        print("[STARTUP] Strategy Orchestrator initialized")
        print(f"  Execution Gateway: Active")
        print(f"  Fee Calculator: Consolidated")
        print("=" * 50)
    except Exception as e:
        print(f"[STARTUP] Strategy Orchestrator failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        # Gateway is critical - re-raise to prevent app from starting
        raise RuntimeError(f"Failed to initialize ExecutionGateway: {e}")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop Strategy Orchestrator first
    try:
        orchestrator = routes.get_orchestrator()
        if orchestrator and orchestrator._is_running:
            await orchestrator.stop()
            print("[SHUTDOWN] Strategy Orchestrator stopped")
    except Exception as e:
        print(f"[SHUTDOWN] Error stopping Strategy Orchestrator: {e}")

    # Stop AutoTrader
    if routes.auto_trader_instance and routes.auto_trader_instance.is_running:
        await routes.auto_trader_instance.stop()
        print("[SHUTDOWN] AutoTrader stopped")

    # Shutdown BTC arbitrage engine
    try:
        btc_arb_engine = routes.get_btc_arb_engine()
        await btc_arb_engine.stop()
        print("[SHUTDOWN] BTC Arbitrage Engine stopped")
    except Exception as e:
        print(f"[SHUTDOWN] Error stopping BTC arbitrage engine: {e}")

    # Gateway cleanup (no explicit shutdown but we log it)
    logger.info("ExecutionGateway stopped")
    print("[SHUTDOWN] ExecutionGateway stopped")

    print("Shutdown complete.")


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

# Prediction routes (weather forecasting and bracket analysis)
app.include_router(prediction_router, prefix="/api")

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
