# Refactoring Plan - Kalshi Arbitrage Platform

**Generated:** 2025-01-15
**Priority:** Critical bugs first, then architecture improvements

---

## Executive Summary

The codebase has grown organically with 78 Python files (~77,500 lines) and 43 TypeScript files (~6,139 lines). While functional, there are 4 critical bugs that must be fixed before live trading, and several architectural improvements needed for maintainability.

---

## Phase 1: Critical Bug Fixes (BLOCKING)

**Must complete before ANY live trading.**

| Priority | Bug | Location | Impact |
|----------|-----|----------|--------|
| P0 | Fee not in edge calc | `weather_strategy.py:333-338` | Shows 2% profit when actual is -6.5% loss |
| P0 | No partial fill rollback | `batch_executor.py:255-290` | Unhedged positions on failures |
| P1 | Cache stale on partial | `execution_gateway.py:294-297` | 30s stale data after executions |
| P2 | Bracket label off-by-1 | `kalshi_models.py:265-273` | Incorrect temperature display |

**See `CRITICAL_FIXES.md` for copy-paste solutions.**

---

## Phase 2: Architecture Consolidation

### 2.1 Unify Fee Calculation

**Problem:** Fee calculation exists in 4 places with inconsistent implementations.

**Current State:**
```
backend/services/core/fee_calculator.py    # Primary (correct)
backend/config/fees.py                     # Legacy duplicate
backend/services/arbitrage_calculator.py   # Inline calculation
backend/services/strategies/weather_strategy.py  # Missing entirely!
```

**Target State:**
- Single source: `backend/services/core/fee_calculator.py`
- All strategies import from core
- Delete duplicate implementations

**Refactoring Steps:**
1. Add deprecation warnings to `backend/config/fees.py`
2. Update all imports to use `core.fee_calculator`
3. Remove inline fee calculations in strategies
4. Delete `backend/config/fees.py` after migration

### 2.2 Consolidate Execution Paths

**Problem:** 4 different execution entry points with inconsistent behavior.

**Current State:**
```
ExecutionGateway.execute()         # Core path
BatchExecutor.execute_batch()      # Lower-level
TradeExecutor.execute_trade()      # Legacy paper trading
BTCArbitrageEngine.execute()       # Strategy-specific
```

**Target State:**
- Single entry point: `ExecutionGateway.execute()`
- All strategies route through gateway
- Gateway handles paper/live routing internally

**Refactoring Steps:**
1. Add `source` parameter to `ExecutionGateway.execute()`
2. Update strategies to use gateway exclusively
3. Move paper trading logic into gateway
4. Deprecate `TradeExecutor` class

### 2.3 Database Schema Migration

**Problem:** v1 and v2 tables coexist with no migration path.

**Current Tables:**
```sql
-- v1 (legacy)
daily_pnl          -- Basic P&L tracking
trading_signals    -- Simple signal storage

-- v2 (current)
daily_pnl_v2       -- Enhanced with win/loss stats
signals_v2         -- Unified with strategy_type
```

**Target State:**
- Single set of tables (drop v1)
- Migration script for existing data
- Foreign key constraints enabled

**Refactoring Steps:**
1. Create migration script to copy v1 → v2
2. Update all code to use v2 tables
3. Add foreign key constraints
4. Drop v1 tables in follow-up release

---

## Phase 3: Code Organization

### 3.1 Service Layer Cleanup

**Problem:** Services have unclear boundaries and circular dependencies.

**Current Issues:**
- `kalshi_client.py` (800+ lines) does too much
- Strategy classes duplicate market fetching logic
- No clear interface contracts

**Proposed Structure:**
```
backend/services/
├── api/                    # External API clients
│   ├── kalshi_client.py    # Kalshi REST/WS only
│   ├── nws_client.py       # NWS weather only
│   └── spot_price_client.py
├── core/                   # Trading infrastructure
│   ├── execution_gateway.py
│   ├── fee_calculator.py
│   ├── risk_manager.py
│   └── position_manager.py
├── strategies/             # Strategy implementations
│   ├── base_strategy.py
│   ├── weather_strategy.py
│   └── btc_strategy.py
└── scanners/               # Market scanners
    ├── weather_scanner.py
    └── btc_scanner.py
```

**Refactoring Steps:**
1. Extract API client methods from `kalshi_client.py`
2. Create `api/` subdirectory for external clients
3. Move scanner logic to `scanners/` subdirectory
4. Update imports throughout codebase

### 3.2 Type Safety Improvements

**Problem:** Mixed use of dataclasses, Pydantic, and plain dicts.

**Current Issues:**
```python
# Inconsistent return types
def get_markets() -> List[Dict]      # Some return dicts
def get_markets() -> List[Market]    # Some return models
```

**Target State:**
- Pydantic models for all API boundaries
- Dataclasses for internal data structures
- No raw dicts in function signatures

**Refactoring Steps:**
1. Audit all function return types
2. Define Pydantic response models in `models/responses.py`
3. Update services to return typed models
4. Add type hints to all public functions

---

## Phase 4: Testing Infrastructure

### 4.1 Add Integration Tests

**Current Coverage:** Unit tests only, no integration tests.

**Required Test Suites:**
```
tests/
├── unit/                 # Existing
├── integration/          # NEW
│   ├── test_execution_flow.py
│   ├── test_scanner_flow.py
│   └── test_settlement_flow.py
└── e2e/                  # NEW (paper mode only)
    └── test_full_trade_cycle.py
```

**Refactoring Steps:**
1. Create `tests/integration/` directory
2. Add pytest fixtures for database setup
3. Write execution flow integration tests
4. Add CI pipeline for integration tests

### 4.2 Mock Infrastructure

**Problem:** Tests require live API access.

**Required Mocks:**
- `MockKalshiClient` - Simulates Kalshi API
- `MockNWSClient` - Returns canned weather data
- `MockSpotPriceClient` - Fixed BTC prices

**Refactoring Steps:**
1. Create `tests/mocks/` directory
2. Implement mock clients with realistic responses
3. Update tests to use mocks by default
4. Add `--live` flag for real API tests

---

## Phase 5: Documentation

### 5.1 API Documentation

**Problem:** No OpenAPI/Swagger documentation.

**Target:**
- FastAPI automatic docs at `/docs`
- Response models documented
- Example requests/responses

**Refactoring Steps:**
1. Add response models to all endpoints
2. Add docstrings to route handlers
3. Configure Swagger UI theme
4. Add authentication examples

### 5.2 Code Documentation

**Problem:** Inconsistent docstrings and comments.

**Target:**
- All public functions have docstrings
- Complex algorithms explained
- Known issues documented inline

**Refactoring Steps:**
1. Run `pydocstyle` to find missing docstrings
2. Add docstrings to core modules first
3. Document fee calculation thoroughly
4. Add "WARNING" comments for critical code paths

---

## Implementation Roadmap

### Immediate (Before Live Trading)
- [ ] Fix 4 critical bugs (Phase 1)
- [ ] Add integration test for execution flow
- [ ] Document fee calculation formula

### Short-term (1-2 sprints)
- [ ] Unify fee calculation (Phase 2.1)
- [ ] Consolidate execution paths (Phase 2.2)
- [ ] Add mock infrastructure

### Medium-term (3-4 sprints)
- [ ] Database migration (Phase 2.3)
- [ ] Service layer cleanup (Phase 3.1)
- [ ] Type safety improvements (Phase 3.2)

### Long-term (5+ sprints)
- [ ] Full test coverage
- [ ] API documentation
- [ ] Performance optimization

---

## Risk Assessment

| Refactoring | Risk | Mitigation |
|-------------|------|------------|
| Fee unification | Medium | Extensive testing, parallel run |
| Execution consolidation | High | Feature flag, gradual rollout |
| Database migration | High | Backup, rollback script |
| Service reorganization | Low | No behavior changes |

---

## Success Metrics

- [ ] All 4 critical bugs fixed
- [ ] Integration test suite passing
- [ ] Zero duplicate fee calculations
- [ ] Single execution entry point
- [ ] 80%+ type hint coverage
- [ ] API docs available at `/docs`

---

*Last updated: 2025-01-15*
