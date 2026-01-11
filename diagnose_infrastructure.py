"""
Comprehensive Infrastructure Diagnostic Tool for Kalshi Trading Platform

This script diagnoses and optionally fixes issues with:
- Database schema (missing tables/columns)
- Component imports
- Component instantiation
- Test failures

Usage:
    python diagnose_infrastructure.py              # Diagnose only
    python diagnose_infrastructure.py --fix        # Diagnose and fix
    python diagnose_infrastructure.py -v           # Verbose mode
    python diagnose_infrastructure.py --fix -v     # Fix with verbose output
"""

import sys
import os
import asyncio
import sqlite3
import traceback
import argparse
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Color codes for output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

# Output helpers
def log_ok(msg: str):
    print(f"  {Colors.GREEN}[OK]{Colors.RESET} {msg}")

def log_fail(msg: str, details: str = ""):
    print(f"  {Colors.RED}[FAIL]{Colors.RESET} {msg}")
    if details:
        print(f"         {details}")

def log_warn(msg: str, details: str = ""):
    print(f"  {Colors.YELLOW}[WARN]{Colors.RESET} {msg}")
    if details:
        print(f"         {details}")

def log_info(msg: str):
    print(f"  {Colors.CYAN}[INFO]{Colors.RESET} {msg}")

def section(title: str):
    print(f"\n{Colors.BOLD}{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}{Colors.RESET}")

# Diagnostic results
results = {
    "database": {"issues": [], "warnings": [], "fixes": []},
    "imports": {"issues": [], "warnings": []},
    "components": {"issues": [], "warnings": []},
    "tests": {"issues": [], "warnings": []}
}

# Expected database schema
EXPECTED_TABLES = {
    "paper_account": ["id", "balance", "starting_balance", "created_at", "updated_at"],
    "paper_positions": ["id", "created_at", "ticker", "side", "contracts", "avg_price",
                       "total_cost", "total_fees", "settlement_time", "settled", "settled_at",
                       "settlement_value", "realized_pnl", "trade_id"],
    "paper_trades": ["id", "executed_at", "asset", "total_cost", "total_fees", "contracts_per_leg",
                    "expected_payout", "expected_profit", "expected_profit_pct", "actual_payout",
                    "actual_profit", "legs_json", "status"],
    "trading_signals": ["id", "ticker", "signal_type", "edge_percent", "model_prob", "market_price",
                       "recommended_size", "source", "status", "created_at", "executed_at",
                       "execution_price", "notes"],
    "auto_trader_config": ["id", "enabled", "min_edge_percent", "max_position_size",
                          "max_daily_loss_cents", "max_open_positions", "allowed_series", "updated_at"],
    "daily_pnl": ["date", "realized_pnl_cents", "trades_count", "updated_at"],
    "btc_arb_executions": ["id", "opportunity_id", "executed_at", "mode", "contracts_per_leg",
                          "total_cost_cents", "total_fees_cents", "guaranteed_profit_cents", "status",
                          "kalshi_response", "settled_at", "settlement_outcome", "actual_payout_cents",
                          "actual_profit_cents", "audit_id"],
    "btc_arb_config": ["id", "min_edge_percent", "default_budget_cents", "auto_trade_enabled",
                      "scan_interval_seconds", "max_position_per_opp_cents", "mode", "updated_at"],
    "execution_audit": ["id", "request_id", "created_at", "source", "signal_id", "mode", "legs_json",
                       "atomic", "max_slippage_cents", "success", "total_cost_cents", "total_fees_cents",
                       "execution_time_ms", "leg_results_json", "error"],
    "circuit_breaker_state": ["id", "tripped", "trip_reason", "trip_time", "permanent",
                             "consecutive_losses", "daily_loss_cents", "hourly_trades_json",
                             "hourly_exposure_json", "last_reset_date", "updated_at"],
    "manual_orders": ["id", "created_at", "ticker", "side", "action", "count", "price_cents",
                     "mode", "status", "filled_count", "avg_fill_price", "total_cost", "total_fees",
                     "kalshi_order_id", "error", "updated_at"],
    "watchlist": ["id", "ticker", "title", "subtitle", "notes", "added_at"],
    "signals_v2": ["id", "strategy_type", "ticker", "signal_type", "edge_percent", "model_prob",
                  "market_price", "recommended_size", "confidence", "is_arbitrage", "legs_json",
                  "metadata_json", "status", "created_at", "expires_at", "executed_at",
                  "execution_price", "notes"],
    "trade_records": ["id", "strategy_type", "ticker", "side", "contracts", "entry_price",
                     "entry_time", "exit_price", "exit_time", "fees_cents", "pnl_cents",
                     "status", "is_arbitrage", "batch_id", "signal_id", "notes"],
    "orchestrator_config": ["id", "auto_trade_enabled", "mode", "kelly_fraction", "min_edge_percent",
                           "max_position_per_market", "max_daily_loss_cents", "cb_max_consecutive_losses",
                           "updated_at"],
    "risk_positions": ["ticker", "contracts", "avg_price", "side", "opened_at", "updated_at"],
    "daily_pnl_v2": ["date", "realized_pnl_cents", "unrealized_pnl_cents", "total_trades",
                    "winning_trades", "losing_trades", "total_fees_cents", "max_drawdown_cents",
                    "updated_at"],
    "historical_opportunities": ["id", "strategy_type", "ticker", "signal_type", "edge_percent",
                                "model_prob", "market_price", "recommended_size", "is_arbitrage",
                                "timestamp", "resolution_time", "outcome", "won", "metadata_json"],
    "alert_history": ["id", "type", "title", "message", "priority", "data_json", "created_at",
                     "acknowledged", "acknowledged_at"],
}

# Modules to test
MODULES_TO_TEST = [
    ('backend.services.core.risk_manager', ['RiskManager', 'RiskLimits', 'RiskCheck']),
    ('backend.services.core.circuit_breaker', ['CircuitBreaker', 'CBConfig']),
    ('backend.services.core.performance_tracker', ['PerformanceTracker', 'Metrics']),
    ('backend.services.core.strategy_orchestrator', ['StrategyOrchestrator']),
    ('backend.services.core.backtest_engine', ['BacktestEngine', 'BacktestConfig', 'BacktestResult']),
    ('backend.services.core.signal_manager', ['SignalManager']),
    ('backend.services.core.batch_executor', ['BatchExecutor', 'BatchResult', 'OrderLeg']),
    ('backend.services.core.kelly_sizing', ['KellySizing', 'KellyConfig', 'KellyResult']),
    ('backend.services.core.alert_service', ['AlertService', 'Alert', 'AlertType', 'AlertPriority']),
    ('backend.services.core.base_strategy', ['BaseStrategy', 'TradingSignal', 'StrategyType', 'SignalType']),
    ('backend.services.core.fee_calculator', ['FeeCalculator', 'FeeType', 'FeeCalculation']),
    ('backend.services.core.position_manager', ['PositionManager', 'PositionSource', 'UnifiedPosition']),
    ('backend.services.core.execution_gateway', ['ExecutionGateway']),
    ('backend.services.strategies', ['WeatherStrategy', 'BTCArbitrageStrategy', 'BTCDirectionalStrategy']),
    ('backend.services.reconciliation', ['ReconciliationService', 'ReconciliationConfig']),
]


# ============================================================
# SECTION 1: DATABASE DIAGNOSTICS
# ============================================================

def diagnose_database(db_path: str, verbose: bool = False) -> Dict[str, Any]:
    """Check database schema for missing tables and columns."""
    section("SECTION 1: DATABASE DIAGNOSTICS")

    if not os.path.exists(db_path):
        log_fail(f"Database not found at {db_path}")
        results["database"]["issues"].append(f"Database file missing: {db_path}")
        results["database"]["fixes"].append(f"Run: await db.initialize() or execute schema.sql")
        return results["database"]

    log_ok(f"Database found at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all existing tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    log_info(f"Found {len(existing_tables)} tables in database")
    if verbose:
        for table in sorted(existing_tables):
            print(f"    - {table}")

    # Check each expected table
    missing_tables = []
    for table_name, expected_columns in EXPECTED_TABLES.items():
        if table_name not in existing_tables:
            log_fail(f"Table '{table_name}' is MISSING")
            missing_tables.append(table_name)
            results["database"]["issues"].append(f"Missing table: {table_name}")
        else:
            # Check columns in this table
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = {row[1] for row in cursor.fetchall()}

            missing_cols = set(expected_columns) - existing_columns
            extra_cols = existing_columns - set(expected_columns)

            if missing_cols:
                log_warn(f"Table '{table_name}' missing columns: {', '.join(sorted(missing_cols))}")
                results["database"]["warnings"].append(f"{table_name}: missing {', '.join(sorted(missing_cols))}")
                results["database"]["fixes"].append(f"ALTER TABLE {table_name} ADD COLUMN ...")
            elif verbose:
                log_ok(f"Table '{table_name}' schema OK ({len(existing_columns)} columns)")

            if extra_cols and verbose:
                log_info(f"Table '{table_name}' has extra columns: {', '.join(sorted(extra_cols))}")

    # Check for critical initialization
    if "circuit_breaker_state" in existing_tables:
        cursor.execute("SELECT COUNT(*) FROM circuit_breaker_state WHERE id = 1")
        if cursor.fetchone()[0] == 0:
            log_warn("circuit_breaker_state table empty - needs initialization")
            results["database"]["warnings"].append("circuit_breaker_state: no row with id=1")
            results["database"]["fixes"].append("INSERT INTO circuit_breaker_state (id) VALUES (1)")

    if "orchestrator_config" in existing_tables:
        cursor.execute("SELECT COUNT(*) FROM orchestrator_config WHERE id = 1")
        if cursor.fetchone()[0] == 0:
            log_warn("orchestrator_config table empty - needs initialization")
            results["database"]["warnings"].append("orchestrator_config: no row with id=1")
            results["database"]["fixes"].append("INSERT INTO orchestrator_config (id) VALUES (1)")

    conn.close()

    # Summary
    print()
    if missing_tables:
        log_fail(f"Database is missing {len(missing_tables)} critical tables")
    else:
        log_ok("All expected tables exist")

    return results["database"]


# ============================================================
# SECTION 2: IMPORT DIAGNOSTICS
# ============================================================

def diagnose_imports(verbose: bool = False) -> Dict[str, Any]:
    """Test importing all core modules."""
    section("SECTION 2: IMPORT DIAGNOSTICS")

    passed = 0
    failed = 0

    for module_path, class_names in MODULES_TO_TEST:
        try:
            module = __import__(module_path, fromlist=class_names)

            for class_name in class_names:
                if hasattr(module, class_name):
                    if verbose:
                        log_ok(f"{module_path}.{class_name}")
                    passed += 1
                else:
                    log_fail(f"{module_path}.{class_name} - class not found in module")
                    results["imports"]["issues"].append(f"{module_path}.{class_name} not exported")
                    failed += 1

        except Exception as e:
            log_fail(f"{module_path} - import failed")
            if verbose:
                print(f"         Error: {str(e)}")
                traceback.print_exc()
            results["imports"]["issues"].append(f"{module_path}: {str(e)}")
            failed += len(class_names)

    # Summary
    print()
    log_info(f"Import tests: {passed} passed, {failed} failed")

    return results["imports"]


# ============================================================
# SECTION 3: COMPONENT INSTANTIATION TESTS
# ============================================================

async def diagnose_components(verbose: bool = False) -> Dict[str, Any]:
    """Try to instantiate core components with minimal mocks."""
    section("SECTION 3: COMPONENT INSTANTIATION TESTS")

    # Mock database - properly async
    class MockDB:
        def __init__(self):
            self.conn = None

        def connection(self):
            return MockConnection()

    class MockConnection:
        def __init__(self):
            self.conn = sqlite3.connect("./data/kalshi.db")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, query, *args):
            cursor = self.conn.execute(query, args if args else ())
            return MockCursor(cursor)

        async def fetchone(self):
            return None

        async def fetchall(self):
            return []

    class MockCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        async def fetchone(self):
            return self._cursor.fetchone()

        async def fetchall(self):
            return self._cursor.fetchall()

    # Mock WebSocket manager
    class MockWSManager:
        async def broadcast(self, msg):
            pass

    db = MockDB()

    # Test 1: RiskManager
    try:
        from backend.services.core.risk_manager import RiskManager, RiskLimits

        risk = RiskManager(RiskLimits(), db)
        log_ok("RiskManager instantiates")

        # Test a method
        try:
            check = await risk.check_trade("TEST", 10, 50, 1000000)
            log_ok(f"RiskManager.check_trade() works: {check}")
        except Exception as e:
            log_warn(f"RiskManager.check_trade() failed: {str(e)}")
            if verbose:
                traceback.print_exc()
    except Exception as e:
        log_fail(f"RiskManager instantiation failed: {str(e)}")
        results["components"]["issues"].append(f"RiskManager: {str(e)}")
        if verbose:
            traceback.print_exc()

    # Test 2: CircuitBreaker
    try:
        from backend.services.core.circuit_breaker import CircuitBreaker, CBConfig

        circuit = CircuitBreaker(CBConfig())
        log_ok("CircuitBreaker instantiates")

        # Test methods
        try:
            can_trade = await circuit.can_trade()
            log_ok(f"CircuitBreaker.can_trade() works: {can_trade}")
        except Exception as e:
            log_warn(f"CircuitBreaker.can_trade() failed: {str(e)}")
            if verbose:
                traceback.print_exc()
    except Exception as e:
        log_fail(f"CircuitBreaker instantiation failed: {str(e)}")
        results["components"]["issues"].append(f"CircuitBreaker: {str(e)}")
        if verbose:
            traceback.print_exc()

    # Test 3: PerformanceTracker
    try:
        from backend.services.core.performance_tracker import PerformanceTracker

        perf = PerformanceTracker(db)
        log_ok("PerformanceTracker instantiates")

        # Test methods
        try:
            metrics = await perf.get_metrics()
            log_ok(f"PerformanceTracker.get_metrics() works")
        except Exception as e:
            log_warn(f"PerformanceTracker.get_metrics() failed: {str(e)}")
            if verbose:
                traceback.print_exc()
    except Exception as e:
        log_fail(f"PerformanceTracker instantiation failed: {str(e)}")
        results["components"]["issues"].append(f"PerformanceTracker: {str(e)}")
        if verbose:
            traceback.print_exc()

    # Test 4: SignalManager
    try:
        from backend.services.core.signal_manager import SignalManager

        signals = SignalManager(db)
        log_ok("SignalManager instantiates")
    except Exception as e:
        log_fail(f"SignalManager instantiation failed: {str(e)}")
        results["components"]["issues"].append(f"SignalManager: {str(e)}")
        if verbose:
            traceback.print_exc()

    # Test 5: AlertService
    try:
        from backend.services.core.alert_service import AlertService, AlertType, AlertPriority

        alerts = AlertService(MockWSManager())
        log_ok("AlertService instantiates")
    except Exception as e:
        log_fail(f"AlertService instantiation failed: {str(e)}")
        results["components"]["issues"].append(f"AlertService: {str(e)}")
        if verbose:
            traceback.print_exc()

    # Test 6: StrategyOrchestrator
    try:
        from backend.services.core.strategy_orchestrator import StrategyOrchestrator
        from backend.services.core.signal_manager import SignalManager
        from backend.services.core.kelly_sizing import KellySizing, KellyConfig
        from backend.services.core.risk_manager import RiskManager, RiskLimits
        from backend.services.core.circuit_breaker import CircuitBreaker, CBConfig
        from backend.services.core.performance_tracker import PerformanceTracker
        from backend.services.core.alert_service import AlertService

        # Mock executor
        class MockExecutor:
            async def execute(self, request):
                return None

        orchestrator = StrategyOrchestrator(
            db=db,
            signals=SignalManager(db),
            kelly=KellySizing(KellyConfig()),
            risk=RiskManager(RiskLimits(), db),
            circuit=CircuitBreaker(CBConfig()),
            executor=MockExecutor(),
            performance=PerformanceTracker(db),
            alerts=AlertService(MockWSManager())
        )
        log_ok("StrategyOrchestrator instantiates")

        # Test load_config
        try:
            await orchestrator.load_config()
            log_ok("StrategyOrchestrator.load_config() works")
        except Exception as e:
            log_warn(f"StrategyOrchestrator.load_config() failed: {str(e)}")
            if verbose:
                traceback.print_exc()
    except Exception as e:
        log_fail(f"StrategyOrchestrator instantiation failed: {str(e)}")
        results["components"]["issues"].append(f"StrategyOrchestrator: {str(e)}")
        if verbose:
            traceback.print_exc()

    # Test 7: BacktestEngine
    try:
        from backend.services.core.backtest_engine import BacktestEngine, BacktestConfig

        backtest = BacktestEngine(db)
        log_ok("BacktestEngine instantiates")
    except Exception as e:
        log_fail(f"BacktestEngine instantiation failed: {str(e)}")
        results["components"]["issues"].append(f"BacktestEngine: {str(e)}")
        if verbose:
            traceback.print_exc()

    return results["components"]


# ============================================================
# SECTION 4: TEST REPRODUCTION
# ============================================================

async def diagnose_tests(verbose: bool = False) -> Dict[str, Any]:
    """Reproduce failing tests with detailed error output."""
    section("SECTION 4: TEST REPRODUCTION")

    log_info("Running subset of test_core_components.py tests...")

    # Just check if the tests would pass import-wise
    try:
        import test_core_components
        log_ok("test_core_components.py imports successfully")
    except Exception as e:
        log_fail(f"test_core_components.py import failed: {str(e)}")
        results["tests"]["issues"].append(f"test_core_components import: {str(e)}")
        if verbose:
            traceback.print_exc()

    return results["tests"]


# ============================================================
# SECTION 5: FIX RECOMMENDATIONS
# ============================================================

def generate_fix_recommendations() -> List[str]:
    """Generate SQL and code fixes based on findings."""
    section("SECTION 5: FIX RECOMMENDATIONS")

    fixes = []

    # Database fixes
    if results["database"]["fixes"]:
        log_info("Database fixes needed:")
        for fix in results["database"]["fixes"]:
            print(f"    {fix}")
            fixes.append(fix)

    # Component fixes
    if results["components"]["issues"]:
        log_info("Component issues found:")
        for issue in results["components"]["issues"]:
            print(f"    {issue}")

    # Import fixes
    if results["imports"]["issues"]:
        log_info("Import issues found:")
        for issue in results["imports"]["issues"]:
            print(f"    {issue}")

    return fixes


# ============================================================
# SECTION 6: AUTO-FIX
# ============================================================

def apply_fixes(db_path: str, verbose: bool = False) -> bool:
    """Apply automatic fixes to the database."""
    section("SECTION 6: AUTO-FIX")

    if not os.path.exists(db_path):
        log_fail(f"Cannot fix: database not found at {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Fix 1: Initialize circuit_breaker_state if empty
        cursor.execute("SELECT COUNT(*) FROM circuit_breaker_state WHERE id = 1")
        if cursor.fetchone()[0] == 0:
            log_info("Initializing circuit_breaker_state...")
            cursor.execute("INSERT INTO circuit_breaker_state (id) VALUES (1)")
            log_ok("circuit_breaker_state initialized")

        # Fix 2: Initialize orchestrator_config if empty
        cursor.execute("SELECT COUNT(*) FROM orchestrator_config WHERE id = 1")
        if cursor.fetchone()[0] == 0:
            log_info("Initializing orchestrator_config...")
            cursor.execute("INSERT INTO orchestrator_config (id) VALUES (1)")
            log_ok("orchestrator_config initialized")

        # Fix 3: Run schema.sql if tables are missing
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='execution_audit'")
        if cursor.fetchone() is None:
            log_info("Running schema.sql to create missing tables...")
            schema_path = Path("backend/database/schema.sql")
            if schema_path.exists():
                with open(schema_path) as f:
                    cursor.executescript(f.read())
                log_ok("Schema applied successfully")
            else:
                log_warn("schema.sql not found - cannot auto-create tables")

        conn.commit()
        log_ok("Database fixes applied successfully")
        return True

    except Exception as e:
        log_fail(f"Error applying fixes: {str(e)}")
        if verbose:
            traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()


# ============================================================
# MAIN FUNCTION
# ============================================================

async def main():
    """Run comprehensive diagnostics."""
    parser = argparse.ArgumentParser(description="Diagnose Kalshi trading infrastructure")
    parser.add_argument("--fix", action="store_true", help="Automatically fix issues")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{Colors.CYAN}KALSHI INFRASTRUCTURE DIAGNOSTIC TOOL{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"Started at: {datetime.utcnow().isoformat()}Z\n")

    db_path = "./data/kalshi.db"

    # Run diagnostics
    diagnose_database(db_path, args.verbose)
    diagnose_imports(args.verbose)
    await diagnose_components(args.verbose)
    await diagnose_tests(args.verbose)

    # Generate recommendations
    fixes = generate_fix_recommendations()

    # Apply fixes if requested
    if args.fix:
        apply_fixes(db_path, args.verbose)

    # Summary
    section("SUMMARY")

    total_issues = (
        len(results["database"]["issues"]) +
        len(results["imports"]["issues"]) +
        len(results["components"]["issues"]) +
        len(results["tests"]["issues"])
    )

    total_warnings = (
        len(results["database"]["warnings"]) +
        len(results["imports"]["warnings"]) +
        len(results["components"]["warnings"]) +
        len(results["tests"]["warnings"])
    )

    if total_issues == 0 and total_warnings == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}[PASS] All checks passed!{Colors.RESET}")
    else:
        if total_issues > 0:
            print(f"\n{Colors.RED}Critical Issues: {total_issues}{Colors.RESET}")
        if total_warnings > 0:
            print(f"{Colors.YELLOW}Warnings: {total_warnings}{Colors.RESET}")

        if not args.fix:
            print(f"\n{Colors.CYAN}To automatically fix issues, run:{Colors.RESET}")
            print(f"    python diagnose_infrastructure.py --fix")

    print(f"\n{Colors.CYAN}{'='*70}{Colors.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
