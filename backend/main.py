from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from .api.routes import router
from .api.websocket import websocket_endpoint, manager as ws_manager
from .api.websocket_routes import router as ws_router
from .api.prediction_routes import router as prediction_router
from .database.connection import db
from .config import get_settings

# Core infrastructure
from .services.core.execution_gateway import ExecutionGateway
from .services.core.fee_calculator import FeeCalculator
from .services.core.position_manager import PositionManager, PositionConfig
from .services.core.signal_manager import SignalManager
from .services.core.kelly_sizing import KellySizing, KellyConfig
from .services.core.risk_manager import RiskManager, RiskLimits
from .services.core.circuit_breaker import CircuitBreaker, CBConfig
from .services.core.performance_tracker import PerformanceTracker
from .services.core.alert_service import AlertService
from .services.core.strategy_orchestrator import StrategyOrchestrator

# Services
from .services.paper_trading import PaperTradingService
from .services.kalshi_client import KalshiClient
from .services.nws.client import NWSProductionClient
from .services.spot_price_client import SpotPriceClient
# REMOVED: Legacy engines (now using StrategyOrchestrator)
# from .services.auto_trader import AutoTrader
# from .services.btc_arb_engine import BTCArbitrageEngine
from .services.reconciliation import ReconciliationService, ReconciliationConfig

# Scanners (for UI data - separate from strategies)
from .services.weather_arb_scanner import WeatherArbScanner
from .services.scanner_db import ScannerDatabase

# Strategies
from .services.strategies import (
    WeatherStrategy,
    BTCArbitrageStrategy,
    BTCDirectionalStrategy
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    settings = get_settings()

    # ═══════════════════════════════════════════════════════════════
    # DATABASE
    # ═══════════════════════════════════════════════════════════════
    await db.initialize()

    # ═══════════════════════════════════════════════════════════════
    # CLIENTS
    # ═══════════════════════════════════════════════════════════════
    kalshi_client = KalshiClient() if settings.has_kalshi_credentials else None
    nws_client = NWSProductionClient()
    spot_client = SpotPriceClient()

    # ═══════════════════════════════════════════════════════════════
    # CORE INFRASTRUCTURE
    # ═══════════════════════════════════════════════════════════════

    # Core components
    signals = SignalManager(db)
    kelly = KellySizing(KellyConfig())
    risk = RiskManager(RiskLimits(), db)
    circuit = CircuitBreaker(CBConfig())
    performance = PerformanceTracker(db)
    alerts = AlertService(ws_manager)

    # Fee calculator (consolidated)
    fee_calculator = FeeCalculator()
    logger.info("Fee calculator initialized")

    # Paper trading service
    paper_service = PaperTradingService()
    logger.info("Paper trading service initialized")

    # Execution gateway (single entry point for all trades)
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

    # Position manager (unified position tracking)
    position_manager = PositionManager(
        kalshi_client=kalshi_client,
        db=db,
        config=PositionConfig()
    )
    logger.info("PositionManager initialized")

    # ═══════════════════════════════════════════════════════════════
    # STRATEGIES
    # ═══════════════════════════════════════════════════════════════

    weather_strategy = WeatherStrategy(
        kalshi_client=kalshi_client,
        nws_client=nws_client
    )
    logger.info("WeatherStrategy initialized")

    btc_arb_strategy = BTCArbitrageStrategy(
        kalshi_client=kalshi_client
    )
    logger.info("BTCArbitrageStrategy initialized")

    btc_directional_strategy = BTCDirectionalStrategy(
        kalshi_client=kalshi_client,
        spot_client=spot_client
    )
    logger.info("BTCDirectionalStrategy initialized")

    # ═══════════════════════════════════════════════════════════════
    # ORCHESTRATOR
    # ═══════════════════════════════════════════════════════════════

    orchestrator = StrategyOrchestrator(
        db=db,
        signals=signals,
        kelly=kelly,
        risk=risk,
        circuit=circuit,
        executor=gateway,  # Gateway implements executor interface
        performance=performance,
        alerts=alerts
    )

    # Register strategies
    orchestrator.register(weather_strategy)
    orchestrator.register(btc_arb_strategy)
    orchestrator.register(btc_directional_strategy)
    logger.info(f"Registered {len(orchestrator._strategies)} strategies with orchestrator")

    # Load saved config
    await orchestrator.load_config()

    # Register with routes module
    from .api import routes
    routes.set_orchestrator(orchestrator)

    # ═══════════════════════════════════════════════════════════════
    # START SCANNING (replaces external scanner process)
    # ═══════════════════════════════════════════════════════════════
    # The orchestrator handles all scanning internally.
    # No need for external run_scanners.py anymore.
    if settings.auto_start_scanning:
        await orchestrator.start()
        logger.info("Orchestrator scanning started automatically")
    else:
        logger.info("Orchestrator ready (scanning not auto-started)")

    # ═══════════════════════════════════════════════════════════════
    # BACKGROUND SCANNERS (for UI data)
    # ═══════════════════════════════════════════════════════════════
    # These scanners populate scanner_db with detailed market data
    # for the frontend UI (separate from strategy signals)
    scanner_db = ScannerDatabase()
    weather_scanner = WeatherArbScanner(kalshi_client)
    scanner_task = None

    async def run_scanners_background():
        """Background task to run scanners and populate scanner_db."""
        while True:
            try:
                # Run weather scanner
                weather_result = await weather_scanner.scan_once()
                scanner_db.save_scanner_result("weather", weather_result)
                logger.debug(f"Weather scan completed: {weather_result.get('scan_count', 0)} scans")
            except Exception as e:
                logger.error(f"Scanner error: {e}")
            await asyncio.sleep(settings.weather_scan_interval)

    if settings.auto_start_scanning:
        scanner_task = asyncio.create_task(run_scanners_background())
        logger.info("Background scanners started (weather)")
        app.state.scanner_task = scanner_task

    # ═══════════════════════════════════════════════════════════════
    # RECONCILIATION
    # ═══════════════════════════════════════════════════════════════

    reconciler = ReconciliationService(
        kalshi_client=kalshi_client,
        position_manager=position_manager,
        alert_service=alerts,
        circuit_breaker=circuit,
        db=db,
        config=ReconciliationConfig()
    )
    logger.info("ReconciliationService initialized")

    # ═══════════════════════════════════════════════════════════════
    # STORE ON APP.STATE
    # ═══════════════════════════════════════════════════════════════

    app.state.kalshi_client = kalshi_client
    app.state.paper_service = paper_service
    app.state.circuit_breaker = circuit
    app.state.risk_manager = risk
    app.state.alert_service = alerts
    app.state.orchestrator = orchestrator
    app.state.gateway = gateway
    app.state.position_manager = position_manager
    app.state.fee_calculator = fee_calculator
    app.state.reconciler = reconciler
    app.state.nws_client = nws_client
    app.state.spot_client = spot_client

    # ═══════════════════════════════════════════════════════════════
    # STARTUP BANNER
    # ═══════════════════════════════════════════════════════════════

    print("=" * 60)
    print("   KALSHI TRADING PLATFORM")
    print("=" * 60)
    print(f"   Mode: {'PAPER' if settings.paper_trading_mode else 'LIVE'}")
    print(f"   API Configured: {settings.has_kalshi_credentials}")
    print(f"   Database: {settings.database_path}")
    print(f"   Gateway: Active")
    print(f"   Strategies: {len(orchestrator._strategies)}")
    print(f"   Reconciliation: Ready")
    print("=" * 60)

    if not settings.paper_trading_mode:
        print("   WARNING: Live trading is enabled!")
        print("   WARNING: Real money will be used for trades!")
        print("=" * 60)

    yield

    # ═══════════════════════════════════════════════════════════════
    # SHUTDOWN
    # ═══════════════════════════════════════════════════════════════

    print("\nShutting down...")
    logger.info("Shutting down...")

    # Stop Strategy Orchestrator
    try:
        if orchestrator._is_running:
            await orchestrator.stop()
            print("[SHUTDOWN] Strategy Orchestrator stopped")
    except Exception as e:
        print(f"[SHUTDOWN] Error stopping Strategy Orchestrator: {e}")

    # Stop background scanner task
    try:
        if scanner_task and not scanner_task.done():
            scanner_task.cancel()
            try:
                await scanner_task
            except asyncio.CancelledError:
                pass
            print("[SHUTDOWN] Background scanners stopped")
    except Exception as e:
        print(f"[SHUTDOWN] Error stopping scanners: {e}")

    # Stop ReconciliationService
    try:
        if reconciler:
            await reconciler.stop()
            print("[SHUTDOWN] ReconciliationService stopped")
    except Exception as e:
        print(f"[SHUTDOWN] Error stopping ReconciliationService: {e}")

    # Save orchestrator config
    try:
        await orchestrator.save_config()
    except Exception as e:
        print(f"[SHUTDOWN] Error saving orchestrator config: {e}")

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
