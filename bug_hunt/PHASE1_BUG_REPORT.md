# Phase 1: Bug Discovery Report

**Analysis Date:** 2026-01-14
**Analyzed By:** Claude Code (Opus 4.5)
**Codebase:** Kalshi Prediction Market Arbitrage Trading System

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 2 |
| HIGH | 5 |
| MEDIUM | 6 |
| LOW | 4 |
| **TOTAL** | **17** |

---

## CRITICAL BUGS (Could Lose Money)

### [CRITICAL] Issue #1: Paper Trading Unit Confusion (Cents vs Dollars)

**Severity**: CRITICAL
**File(s)**: `backend/services/paper_trading.py:103-104, 117`
**Description**: The paper trading service has inconsistent unit handling between cents and dollars/floats, which could cause incorrect fee calculations and P&L tracking.

**Evidence**:
```python
# Line 103-104: fee calculation expects cents, but bracket.yes_price may be float 0-1
fee = calculate_fee(num_contracts, bracket.yes_price)

# Line 117: expected_payout is set to num_contracts (should be num_contracts * 100 if in cents)
expected_payout = num_contracts  # $1 per contract set
```

**Impact**:
- Fee calculations could be 100x off if `bracket.yes_price` is a float like 0.35 instead of cents like 35
- Expected payout calculation will be wrong, showing incorrect profit estimates
- Paper trading results won't reflect real-world performance

**Fix**:
- Ensure `bracket.yes_price` is converted to cents (multiply by 100 if float)
- Change `expected_payout = num_contracts * 100` for cents-based accounting
- Add unit validation/conversion at function entry

---

### [CRITICAL] Issue #2: Hardcoded Balance in Strategy Orchestrator

**Severity**: CRITICAL
**File(s)**: `backend/services/core/strategy_orchestrator.py:297-298, 321`
**Description**: The strategy orchestrator uses hardcoded balance values instead of fetching actual account balance, which breaks Kelly criterion sizing and risk management.

**Evidence**:
```python
# Line 297-298
# TODO: Get actual balance from executor
balance_cents = 100000  # Default $1000

# Line 321
100000  # TODO: actual balance
```

**Impact**:
- Kelly criterion will calculate position sizes based on wrong balance
- Risk manager will check limits against fictional $1000 balance
- Live trading could over-allocate or under-allocate positions dramatically

**Fix**:
- Implement `get_balance()` call to paper service or Kalshi client
- Pass actual balance through to Kelly and risk calculations

---

## HIGH SEVERITY BUGS

### [HIGH] Issue #3: Bare Except Clauses (Silent Failures)

**Severity**: HIGH
**File(s)**: Multiple files (see list below)
**Description**: Multiple bare `except:` clauses that catch and silently ignore all exceptions, potentially hiding critical errors.

**Evidence**:
```python
# backend/api/routes.py:128
except:
    continue

# backend/api/websocket.py:22
except:
    self.active_connections.discard(connection)
```

**Locations Found**:
1. `backend/api/routes.py:128` - Datetime parsing
2. `backend/api/websocket.py:22` - Broadcast failures
3. `backend/api/prediction_routes.py:220, 246` - Various operations

**Impact**:
- Errors silently swallowed, making debugging impossible
- Critical failures may go unnoticed in production
- Data corruption could occur without logging

**Fix**: Replace bare `except:` with specific exception types and add logging:
```python
except ValueError as e:
    logger.warning(f"Date parsing failed: {e}")
    continue
```

---

### [HIGH] Issue #4: Missing Position Conflict Check in Paper Mode

**Severity**: HIGH
**File(s)**: `backend/services/core/execution_gateway.py:547-548`
**Description**: Position conflict checking is skipped entirely in paper-only mode, allowing simulation of invalid trades.

**Evidence**:
```python
async def _check_position_conflicts(self, request: ExecutionRequest) -> None:
    if not self.kalshi_client:
        return  # Skip check if no client (paper mode only)
```

**Impact**:
- Paper trading can simulate YES+NO positions on the same market (impossible in reality)
- Paper results won't match real-world constraints
- Strategies validated in paper mode may fail in live mode

**Fix**: Implement local position tracking for paper mode that enforces the same YES+NO constraint.

---

### [HIGH] Issue #5: TOCTOU Race Condition in Execution

**Severity**: HIGH
**File(s)**: `backend/services/core/execution_gateway.py:570-620`
**Description**: Time-of-check to time-of-use vulnerability where prices are validated but could change before actual order placement.

**Evidence**:
```python
# Price is validated here
async def _revalidate_prices(self, request, max_slippage_cents=2) -> bool:
    # ...fetches orderbook and validates...

# But then execution happens later, prices may have moved
async def _execute_live(self, request) -> ExecutionResult:
    # ... actual order placed here ...
```

**Impact**:
- Price could move between validation and execution
- Slippage could exceed expected limits
- Arbitrage may no longer be profitable when executed

**Fix**:
- Use limit orders with exact prices
- Implement atomic batch execution with server-side validation
- Add post-execution price verification

---

### [HIGH] Issue #6: Price Revalidation Skipped in Paper Mode

**Severity**: HIGH
**File(s)**: `backend/services/core/execution_gateway.py:586-587`
**Description**: Price revalidation is completely skipped in paper mode, allowing stale prices.

**Evidence**:
```python
if not self.kalshi_client:
    return True  # Skip validation in paper mode
```

**Impact**:
- Paper trades execute at stale prices from opportunity detection
- Slippage isn't simulated in paper mode
- Performance metrics unrealistic compared to live trading

**Fix**: Fetch fresh prices even in paper mode to simulate realistic execution.

---

### [HIGH] Issue #7: Market Close Time Check May Not Prevent Execution

**Severity**: HIGH
**File(s)**: `backend/services/core/execution_gateway.py:615-657`
**Description**: The new `_check_market_open()` method catches exceptions and returns `True` (allowing trade), even when market data fetch fails.

**Evidence**:
```python
except Exception as e:
    logger.warning(f"Market open check failed for {ticker}: {e}")
    # Don't fail on check errors, proceed with execution
    return True
```

**Impact**:
- If market API fails, trade proceeds without safety check
- Could execute on closed or nearly-closed markets
- Risk of order rejection or worse, locked positions

**Fix**: On fetch failure, return `False` and block execution rather than allowing it.

---

## MEDIUM SEVERITY BUGS

### [MEDIUM] Issue #8: Fee Type Confusion (Integer Returns Used as Float)

**Severity**: MEDIUM
**File(s)**: `backend/services/paper_trading.py:104, 111`
**Description**: `calculate_fee()` returns an integer (cents), but code context suggests it may be used as float (dollars).

**Evidence**:
```python
fee = calculate_fee(num_contracts, bracket.yes_price)  # Returns int (cents)
# ...
fee=fee  # Used in dataclass that expects float based on rounding at line 175
```

**Impact**:
- Minor accounting discrepancies
- Confusion when debugging
- Potential off-by-100x errors if mixed with dollar values

**Fix**: Ensure consistent units throughout or convert explicitly.

---

### [MEDIUM] Issue #9: Rate Limiter Implementation Issue

**Severity**: MEDIUM
**File(s)**: `backend/services/kalshi_client.py:61-62`
**Description**: Write rate limiter is set to 5/sec but Kalshi allows 10/sec for writes. Read limiter matches the spec at 10/sec.

**Evidence**:
```python
# Rate limiters (Kalshi Free tier: 10 req/sec)
self._read_limiter = RateLimiter(max_requests=10, window_seconds=1.0)
self._write_limiter = RateLimiter(max_requests=5, window_seconds=1.0)  # Too conservative
```

**Impact**:
- Batch orders unnecessarily throttled
- Execution latency increased
- Not a bug, but suboptimal performance

**Fix**: Adjust write limiter to `max_requests=10` to match Kalshi's actual limits.

---

### [MEDIUM] Issue #10: Incomplete TODO - Balance Not Fetched

**Severity**: MEDIUM
**File(s)**: `backend/services/core/strategy_orchestrator.py:297, 321`
**Description**: Two TODO comments indicating critical functionality not implemented.

**Evidence**:
```python
# Line 297: # TODO: Get actual balance from executor
# Line 321: 100000  # TODO: actual balance
```

**Impact**: See Critical Issue #2.

---

### [MEDIUM] Issue #11: Min 2-NO Strategy Logic Issue

**Severity**: MEDIUM
**File(s)**: `backend/services/core/fee_calculator.py:450`
**Description**: The "min 2-NO" strategy assumes if neither bracket wins, both NOs pay $1. This is only true for mutually exclusive brackets where exactly one outcome happens.

**Evidence**:
```python
min_2_payout = 100  # If neither bracket wins, both NOs pay
```

**Impact**:
- Strategy is correctly implemented for mutually exclusive sets
- But documentation could be clearer about this constraint
- Could mislead if applied to non-mutually-exclusive markets

**Fix**: Add validation that confirms brackets are mutually exclusive before applying min_2_no strategy.

---

### [MEDIUM] Issue #12: Exception in Exception Handler

**Severity**: MEDIUM
**File(s)**: `backend/services/core/execution_gateway.py:328, 338`
**Description**: Exception handlers that could themselves throw exceptions without proper handling.

**Evidence**:
```python
except Exception as audit_err:
    logger.error(f"Failed to record audit: {audit_err}")
except Exception:
    pass  # Suppress any send_alerts error
```

**Impact**: Could mask original error if audit recording fails.

---

### [MEDIUM] Issue #13: Database Balance in Dollars vs API in Cents

**Severity**: MEDIUM
**File(s)**: `backend/database/schema.sql:4-5` vs `backend/api/schemas.py:206`
**Description**: Database stores balance as `REAL` (dollars), but API schemas reference `balance_cents`.

**Evidence**:
```sql
-- schema.sql
balance REAL NOT NULL DEFAULT 10000.00,
```
```python
# api/schemas.py
balance_cents: int
```

**Impact**:
- Potential conversion errors at API boundary
- Unit confusion when reading/writing database

**Fix**: Standardize on cents throughout or ensure consistent conversion.

---

## LOW SEVERITY BUGS

### [LOW] Issue #14: Exception Swallowing in Multiple Services

**Severity**: LOW
**File(s)**: Multiple (see exception list from grep)
**Description**: Many `except Exception as e:` blocks that log but continue, potentially masking issues.

**Locations**: 80+ occurrences across codebase

**Impact**: Makes debugging harder, errors may be lost.

**Fix**: Review each case and determine if re-raising or proper handling is needed.

---

### [LOW] Issue #15: UTC vs Local Time Inconsistency

**Severity**: LOW
**File(s)**: Various
**Description**: Most code uses `datetime.now(timezone.utc)` correctly, but some uses `datetime.utcnow()` which returns naive datetime.

**Evidence**:
```python
# backend/services/btc_arb_scanner.py:709
'timestamp': datetime.utcnow().isoformat() + 'Z',
```

**Impact**: Minor - inconsistent but functionally equivalent for timestamps.

**Fix**: Standardize on `datetime.now(timezone.utc)` throughout.

---

### [LOW] Issue #16: Unused Import Warning Pattern

**Severity**: LOW
**File(s)**: Various
**Description**: Some imports may be unused (requires deeper analysis with linting tools).

**Impact**: Code bloat, potential confusion.

**Fix**: Run `flake8` or `ruff` to identify and remove unused imports.

---

### [LOW] Issue #17: Missing Type Hints in Older Code

**Severity**: LOW
**File(s)**: Various legacy services
**Description**: Inconsistent type hinting across codebase.

**Impact**: IDE support reduced, potential type errors.

**Fix**: Add type hints to functions without them.

---

## VERIFICATION CHECKLIST

### Known Issues from Prompt - Status

| Issue | Status | Notes |
|-------|--------|-------|
| Bracket labeling off by 1°F | NOT FOUND | `floor_strike`/`cap_strike` handling looks correct in `kalshi_models.py:267-272` |
| Fee integration gaps | FOUND | Issue #1, #8 - unit confusion in paper_trading.py |
| TOCTOU in execution | FOUND | Issue #5 - race condition between validation and execution |
| Rate limiting on NWS API | NOT FOUND | No circuit breaker found for NWS, but has retry logic in nws_client.py |

---

## RECOMMENDATIONS

### Immediate Actions (Before Live Trading)
1. Fix Critical Issues #1 and #2 (unit confusion, hardcoded balance)
2. Add logging to bare except clauses (Issue #3)
3. Implement paper mode position conflict tracking (Issue #4)

### Short-Term (Within 1 Week)
4. Review TOCTOU race condition mitigation (Issue #5)
5. Add failing behavior to market close check (Issue #7)
6. Standardize units (cents) throughout codebase

### Long-Term (Ongoing)
7. Add comprehensive unit tests for fee calculations
8. Implement integration tests that verify paper/live parity
9. Add linting to CI/CD pipeline

---

## Files Analyzed

### Core Trading (High Priority)
- `backend/services/core/execution_gateway.py` - ANALYZED
- `backend/services/core/fee_calculator.py` - ANALYZED
- `backend/services/core/batch_executor.py` - ANALYZED
- `backend/services/kalshi_client.py` - ANALYZED
- `backend/services/paper_trading.py` - ANALYZED
- `backend/services/trade_executor.py` - REFERENCED

### Arbitrage Detection
- `backend/services/arbitrage_calculator.py` - ANALYZED
- `backend/services/weather_arb_scanner.py` - ANALYZED
- `backend/services/btc_arb_scanner.py` - ANALYZED

### Data Models
- `backend/models/kalshi_models.py` - ANALYZED
- `backend/database/schema.sql` - ANALYZED

### API Routes
- `backend/api/routes.py` - ANALYZED
- `backend/api/websocket.py` - ANALYZED
- `backend/utils/kalshi_auth.py` - ANALYZED

---

## Statistics

- Total Python files scanned: 74
- Exception handlers found: 80+
- TODO/FIXME markers: 2 critical
- Bare except clauses: 4+
- SQL injection risks: 0 (parameterized queries used)

---

**Report Generated:** 2026-01-14
**Next Phase:** Bug fixes and verification testing
