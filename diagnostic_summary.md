# Kalshi Arbitrage System - Diagnostic Report

**Generated:** 2026-01-14T20:34:10.200657

---

## Executive Summary

- **Critical Issues:** 2
- **High Priority Issues:** 1
- **Total Fixes Recommended:** 3

---

## Questions Answered


### Q13: Scanner Runtime History

**Answer:** NO DATA - execution_audit table is empty


**Evidence:**
- Total executions: 0
- Gaps > 10 min: 0
- Unique error types: 0

### Q14: False Positive Detection

**Answer:** No false positives found in paper_trades

**False Positive Count:** 0
**Total Loss:** $0.00

### Q15: Slippage Analysis

**Answer:** Mean slippage: 0¢, P95: 0¢, Rejection rate: 0%

- Mean: 0
- Median: 0
- P95: 0
- Max: 0
- Rejection Rate: 0%

---

## Issues Validated


### Fee Integration Bug

**Status:** CONFIRMED

**Evidence:** WeatherStrategy reports 2.04% edge but actual is -6.54% (inflated by 8.58%). Trade appears profitable ($0.02) but after $0.09 fees, actual profit is $-0.07

**Location:** `backend/services/strategies/weather_strategy.py:333-338`

### Bracket Label Bug

**Status:** NEEDS VERIFICATION

**Evidence:** Code shows cap_strike used directly without adjustment. Need to compare with actual market titles to confirm if -1 adjustment needed.

**Location:** `backend/models/kalshi_models.py:265-273`

### Partial Fill Gap

**Status:** CONFIRMED

**Evidence:** CONFIRMED: No rollback, unwind, or recovery logic found in execution code. Searched batch_executor.py, execution_gateway.py, and position_manager.py for: rollback, unwind, revert, cancel.*partial, close.*position.*fail, offsetting, hedge.*fail, recovery.*trade. Zero matches found.


### Cache Invalidation

**Status:** CONFIRMED

**Evidence:** Cache invalidation at line 294-297 is conditional on result.success. Partial fills set success=False, so cache remains stale until TTL (30s) expires.

**Location:** `backend/services/core/execution_gateway.py:294-297`

---

## Recommended Fixes


### 1. [CRITICAL] Fee Integration Bug in WeatherStrategy

**File:** `backend/services/strategies/weather_strategy.py:333-473`

**Fix:** Replace manual edge calculation with FeeCalculator.analyze_weather_arbitrage() call. Store net_cost and fees in signal metadata.

**Impact:** False positive trades causing real losses

### 2. [CRITICAL] No Rollback for Partial Fills

**File:** `backend/services/core/batch_executor.py:255-290`

**Fix:** Implement rollback handler that sells back partial fills when atomic execution fails. Add watchdog timer for stuck orders.

**Impact:** Unhedged positions on failed atomic trades

### 3. [HIGH] Cache Not Invalidated on Partial Fill

**File:** `backend/services/core/execution_gateway.py:294-297`

**Fix:** Invalidate cache on ANY execution attempt, not just successful ones. Add force_refresh parameter to position queries after trade attempts.

**Impact:** Stale position data for subsequent trades

---

## System Health


### Database: OK

| Table | Rows |
|-------|------|
| alert_history | 0 |
| auto_trader_config | 1 |
| btc_arb_config | 1 |
| btc_arb_executions | 0 |
| circuit_breaker_state | 1 |
| daily_pnl | 0 |
| daily_pnl_v2 | 0 |
| execution_audit | 0 |
| historical_opportunities | 0 |
| manual_orders | 0 |
| opportunity_history | 0 |
| orchestrator_config | 1 |
| paper_account | 1 |
| paper_positions | 0 |
| paper_trades | 0 |
| risk_positions | 0 |
| signals_v2 | 0 |
| sqlite_sequence | 0 |
| trade_records | 0 |
| trading_signals | 0 |
| watchlist | 0 |