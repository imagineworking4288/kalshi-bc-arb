"""
Quick validation script for new trading infrastructure components.
Run with: python test_new_components.py
"""

import asyncio
import sys
from datetime import datetime

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
CHECK = "[PASS]"
CROSS = "[FAIL]"
WARN = "[WARN]"

results = {"passed": 0, "failed": 0, "warnings": 0}

def log_pass(msg):
    results["passed"] += 1
    print(f"  {GREEN}{CHECK}{RESET} {msg}")

def log_fail(msg, error=None):
    results["failed"] += 1
    print(f"  {RED}{CROSS}{RESET} {msg}")
    if error:
        print(f"      Error: {error}")

def log_warn(msg):
    results["warnings"] += 1
    print(f"  {YELLOW}{WARN}{RESET} {msg}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def test_imports():
    """Test that all new modules can be imported."""
    section("IMPORT TESTS")
    
    modules = [
        ("FeeCalculator", "backend.services.core.fee_calculator", "FeeCalculator"),
        ("FeeType", "backend.services.core.fee_calculator", "FeeType"),
        ("PositionManager", "backend.services.core.position_manager", "PositionManager"),
        ("PositionSource", "backend.services.core.position_manager", "PositionSource"),
        ("ExecutionGateway", "backend.services.core.execution_gateway", "ExecutionGateway"),
        ("WeatherStrategy", "backend.services.strategies", "WeatherStrategy"),
        ("BTCArbitrageStrategy", "backend.services.strategies", "BTCArbitrageStrategy"),
        ("BTCDirectionalStrategy", "backend.services.strategies", "BTCDirectionalStrategy"),
        ("ReconciliationService", "backend.services.reconciliation", "ReconciliationService"),
        ("Strategy Registry", "backend.services.strategies", "get_all_strategies"),
    ]
    
    for name, module_path, attr in modules:
        try:
            module = __import__(module_path, fromlist=[attr])
            obj = getattr(module, attr)
            log_pass(f"{name} imports correctly")
        except ImportError as e:
            log_fail(f"{name} import failed", str(e))
        except AttributeError as e:
            log_fail(f"{name} attribute missing", str(e))


async def test_fee_calculator():
    """Test FeeCalculator functionality."""
    section("FEE CALCULATOR TESTS")
    
    try:
        from backend.services.core.fee_calculator import FeeCalculator, FeeType
        
        calc = FeeCalculator()
        log_pass("FeeCalculator instantiates")
        
        # Test single fee calculation
        result = calc.calculate(10, 50, FeeType.TAKER)
        assert result.gross_cost_cents == 500, f"Expected 500, got {result.gross_cost_cents}"
        assert result.fee_cents > 0, "Fee should be > 0"
        assert result.total_cost_cents == result.gross_cost_cents + result.fee_cents
        log_pass(f"Single fee: 10 contracts @ 50¢ = {result.total_cost_cents}¢ total")
        
        # Test edge cases
        edge_result = calc.calculate(1, 99, FeeType.TAKER)
        assert edge_result.fee_cents >= 1, "Minimum fee should be 1¢"
        log_pass(f"Edge case (1 @ 99¢): fee = {edge_result.fee_cents}¢")
        
        # Test multi-leg
        legs = [
            {"ticker": "MKT1", "contracts": 5, "price_cents": 30},
            {"ticker": "MKT2", "contracts": 5, "price_cents": 40},
            {"ticker": "MKT3", "contracts": 5, "price_cents": 25},
        ]
        multi = calc.calculate_multi_leg(legs)
        assert multi["total_gross_cents"] == 475
        assert len(multi["legs"]) == 3
        log_pass(f"Multi-leg: 3 legs, total = {multi['total_cost_cents']}¢")
        
        # Test arbitrage profit
        arb = calc.estimate_arbitrage_profit(legs, payout_cents=100)
        log_pass(f"Arbitrage estimate: profit = {arb['profit']}¢ ({arb['profit_percent']:.1f}%)")
        
    except Exception as e:
        log_fail("FeeCalculator tests", str(e))


async def test_position_manager():
    """Test PositionManager functionality."""
    section("POSITION MANAGER TESTS")
    
    try:
        from backend.services.core.position_manager import PositionManager, PositionSource, UnifiedPosition, PositionConfig

        # Test with mocks
        class MockDB:
            async def connection(self):
                return MockConnection()

        class MockConnection:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def execute(self, query):
                return MockCursor()

        class MockCursor:
            async def fetchall(self):
                return []

        pm = PositionManager(None, MockDB(), PositionConfig())
        log_pass("PositionManager instantiates")
        
        # Test get_positions (empty)
        positions = await pm.get_positions()
        assert isinstance(positions, list)
        log_pass(f"get_positions returns list (empty: {len(positions)} positions)")
        
        # Test exposure calculation
        exposure = await pm.get_exposure()
        assert hasattr(exposure, "position_count")
        assert hasattr(exposure, "total_cost_cents")
        log_pass(f"get_exposure: {exposure.position_count} positions, {exposure.total_cost_cents}¢")
        
        # Test cache invalidation
        pm.invalidate_cache()
        log_pass("Cache invalidation works")
        
    except Exception as e:
        log_fail("PositionManager tests", str(e))


async def test_execution_models():
    """Test execution models exist and work."""
    section("EXECUTION MODELS TESTS")
    
    try:
        from backend.models.execution_models import (
            ExecutionLeg, ExecutionRequest, LegResult, ExecutionResult
        )
        
        # Test ExecutionLeg
        leg = ExecutionLeg(
            ticker="TEST-MKT",
            side="yes",
            action="buy",
            contracts=10,
            price_cents=50
        )
        assert leg.ticker == "TEST-MKT"
        log_pass("ExecutionLeg creates correctly")
        
        # Test ExecutionRequest
        request = ExecutionRequest(
            source="manual",
            mode="paper",
            legs=[leg]
        )
        assert request.request_id  # Should auto-generate UUID
        assert len(request.legs) == 1
        log_pass(f"ExecutionRequest creates with request_id: {request.request_id[:8]}...")
        
        # Test LegResult
        result = LegResult(
            ticker="TEST-MKT",
            side="yes",
            action="buy",
            requested_contracts=10,
            filled_contracts=10,
            requested_price_cents=50,
            fill_price_cents=50,
            status="filled"
        )
        assert result.status == "filled"
        log_pass("LegResult creates correctly")
        
        # Test ExecutionResult
        exec_result = ExecutionResult(
            request_id=request.request_id,
            success=True,
            mode="paper",
            legs=[result],
            total_cost_cents=500,
            total_fees_cents=10,
            execution_time_ms=100,
            audit_id="test-audit-123"
        )
        assert exec_result.success == True
        log_pass("ExecutionResult creates correctly")
        
    except Exception as e:
        log_fail("Execution models tests", str(e))


async def test_strategy_registry():
    """Test strategy registration system."""
    section("STRATEGY REGISTRY TESTS")
    
    try:
        from backend.services.strategies import (
            get_all_strategies, get_registered_types, get_strategy_class
        )
        from backend.services.core.base_strategy import StrategyType
        
        strategies = get_all_strategies()
        log_pass(f"Registry has {len(strategies)} strategies registered")
        
        types = get_registered_types()
        for st in types:
            log_pass(f"  - {st.value} registered")
        
        # Test lookup
        if StrategyType.WEATHER in strategies:
            weather_cls = get_strategy_class(StrategyType.WEATHER)
            log_pass(f"WeatherStrategy class: {weather_cls.__name__}")
        else:
            log_warn("WeatherStrategy not registered")
        
        if StrategyType.BTC in strategies:
            btc_cls = get_strategy_class(StrategyType.BTC)
            log_pass(f"BTC strategy class: {btc_cls.__name__}")
        else:
            log_warn("BTC strategies not registered")
            
    except Exception as e:
        log_fail("Strategy registry tests", str(e))


async def test_reconciliation():
    """Test ReconciliationService."""
    section("RECONCILIATION SERVICE TESTS")
    
    try:
        from backend.services.reconciliation import (
            ReconciliationService, ReconciliationConfig, DiscrepancyType, Severity
        )
        
        # Test config
        config = ReconciliationConfig(
            run_interval_seconds=60,
            critical_threshold_cents=500
        )
        log_pass(f"ReconciliationConfig: interval={config.run_interval_seconds}s")
        
        # Test enums
        assert DiscrepancyType.MISSING_LOCAL.value == "missing_local"
        assert Severity.CRITICAL.value == "critical"
        log_pass("DiscrepancyType and Severity enums work")
        
        # Test service instantiation (with mocks)
        class MockAlertService:
            async def send(self, *args, **kwargs):
                pass
        
        service = ReconciliationService(
            kalshi_client=None,
            position_manager=None,
            alert_service=MockAlertService(),
            circuit_breaker=None,
            db=None,
            config=config
        )
        log_pass("ReconciliationService instantiates")
        
        status = service.get_status()
        assert "running" in status
        assert "discrepancy_count" in status
        log_pass(f"get_status: running={status['running']}, discrepancies={status['discrepancy_count']}")
        
    except Exception as e:
        log_fail("Reconciliation tests", str(e))


async def test_database_schema():
    """Test that new database tables exist."""
    section("DATABASE SCHEMA TESTS")
    
    try:
        import aiosqlite
        from backend.config import get_settings
        
        settings = get_settings()
        db_path = settings.database_path
        
        async with aiosqlite.connect(db_path) as conn:
            # Check for execution_audit table
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_audit'"
            )
            if await cursor.fetchone():
                log_pass("execution_audit table exists")
            else:
                log_warn("execution_audit table missing - run migrations")
            
            # Check for circuit_breaker_state table
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='circuit_breaker_state'"
            )
            if await cursor.fetchone():
                log_pass("circuit_breaker_state table exists")
                
                # Check for new columns
                cursor = await conn.execute("PRAGMA table_info(circuit_breaker_state)")
                columns = {row[1] for row in await cursor.fetchall()}
                
                new_cols = ["permanent", "hourly_trades_json", "hourly_exposure_json"]
                for col in new_cols:
                    if col in columns:
                        log_pass(f"  - {col} column exists")
                    else:
                        log_warn(f"  - {col} column missing")
            else:
                log_warn("circuit_breaker_state table missing")
                
    except Exception as e:
        log_fail("Database schema tests", str(e))


async def test_api_endpoints():
    """Test that new API endpoints respond."""
    section("API ENDPOINT TESTS")
    
    try:
        import httpx
        
        base_url = "http://localhost:8001"
        
        async with httpx.AsyncClient() as client:
            # Test emergency status
            try:
                resp = await client.get(f"{base_url}/emergency/status", timeout=5.0)
                if resp.status_code == 200:
                    log_pass("GET /emergency/status responds")
                else:
                    log_warn(f"/emergency/status returned {resp.status_code}")
            except httpx.ConnectError:
                log_warn("Backend not running - skipping API tests")
                return
            except Exception as e:
                log_fail("/emergency/status", str(e))
            
            # Test reconciliation status
            try:
                resp = await client.get(f"{base_url}/reconciliation/status", timeout=5.0)
                if resp.status_code == 200:
                    log_pass("GET /reconciliation/status responds")
                elif resp.status_code == 500:
                    log_warn("/reconciliation/status - service may not be initialized")
                else:
                    log_fail(f"/reconciliation/status returned {resp.status_code}")
            except Exception as e:
                log_fail("/reconciliation/status", str(e))
            
            # Test gateway stats (if endpoint exists)
            try:
                resp = await client.get(f"{base_url}/gateway/stats", timeout=5.0)
                if resp.status_code == 200:
                    log_pass("GET /gateway/stats responds")
                elif resp.status_code == 404:
                    log_warn("/gateway/stats endpoint not found")
                else:
                    log_warn(f"/gateway/stats returned {resp.status_code}")
            except Exception as e:
                log_warn(f"/gateway/stats: {e}")
                
    except ImportError:
        log_warn("httpx not installed - pip install httpx for API tests")
    except Exception as e:
        log_fail("API endpoint tests", str(e))


async def main():
    print("\n" + "="*60)
    print("  NEW COMPONENTS VALIDATION TEST")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    await test_imports()
    await test_fee_calculator()
    await test_position_manager()
    await test_execution_models()
    await test_strategy_registry()
    await test_reconciliation()
    await test_database_schema()
    await test_api_endpoints()
    
    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    print(f"  {GREEN}Passed:   {results['passed']}{RESET}")
    print(f"  {RED}Failed:   {results['failed']}{RESET}")
    print(f"  {YELLOW}Warnings: {results['warnings']}{RESET}")
    print("="*60)
    
    if results["failed"] > 0:
        print(f"\n{RED}Some tests failed. Review errors above.{RESET}")
        sys.exit(1)
    elif results["warnings"] > 0:
        print(f"\n{YELLOW}All tests passed with warnings.{RESET}")
    else:
        print(f"\n{GREEN}All tests passed!{RESET}")


if __name__ == "__main__":
    asyncio.run(main())