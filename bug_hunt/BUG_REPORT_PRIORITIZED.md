# Prioritized Bug Report

**Generated:** 2026-01-14
**Source:** PHASE1_BUG_REPORT.md (17 issues)
**Framework:** PHASE2_ANALYSIS_FRAMEWORK.md

---

## Executive Summary

| Bucket | Count | Action |
|--------|-------|--------|
| Bucket 1: STOP TRADING | 3 | Fix BEFORE any live trading |
| Bucket 2: BLOCK LIVE MODE | 7 | Fix within 24 hours |
| Bucket 3: DEGRADED PERFORMANCE | 3 | Fix within 1 week |
| Bucket 4: TECHNICAL DEBT | 4 | Fix opportunistically |
| **TOTAL** | **17** | |

---

## GO/NO-GO DECISION

| Question | Answer | Implication |
|----------|--------|-------------|
| Are there CRITICAL issues? | **YES (3)** | DO NOT proceed to live trading |
| Issues touching execution path? | **7** | Full code review of execution_gateway.py needed |
| Cascading issues? | **YES** | Must fix in dependency order |
| Fee calculation correct? | **YES** | Fee calculator formula is correct |

**DECISION: NO-GO for live trading until Bucket 1 cleared**

---

## Bucket 1: STOP TRADING (Fix Immediately)

These issues could cause financial loss. **Must fix before ANY live trading.**

### STOP-001: Paper Trading Unit Confusion (Cents vs Dollars)
**Original:** Issue #1 (CRITICAL)
**File(s):** `backend/services/paper_trading.py:103-104, 117`
**Problem:** `bracket.yes_price` may be float 0-1 instead of cents 1-99, causing 100x fee calculation errors
**Dependencies:** None - fix first
**Validation:**
```bash
python -c "from backend.services.paper_trading import PaperTradingService; print('OK')"
```

### STOP-002: Hardcoded Balance in Strategy Orchestrator
**Original:** Issue #2 (CRITICAL) + Issue #10 (MEDIUM)
**File(s):** `backend/services/core/strategy_orchestrator.py:297-298, 321`
**Problem:** Kelly criterion and risk manager use fictional $1000 balance instead of actual balance
**Dependencies:** None - can fix in parallel with STOP-001
**Validation:**
```bash
# Verify balance is fetched dynamically
grep -n "balance_cents = " backend/services/core/strategy_orchestrator.py
```

### STOP-003: TOCTOU Race Condition in Execution
**Original:** Issue #5 (HIGH)
**File(s):** `backend/services/core/execution_gateway.py:570-620`
**Problem:** Price validated, then changes before order placed
**Dependencies:** None - can fix in parallel
**Validation:**
- Use limit orders with exact prices
- Verify atomic batch execution

---

## Bucket 2: BLOCK LIVE MODE (Fix Before Production)

These issues break core functionality. **Fix within 24 hours.**

### BLOCK-001: Bare Except Clauses (Silent Failures)
**Original:** Issue #3 (HIGH)
**File(s):**
- `backend/api/routes.py:128`
- `backend/api/websocket.py:22`
- `backend/api/prediction_routes.py:220, 246`
**Problem:** Errors silently swallowed, making debugging impossible
**Dependencies:** None
**Fix:** Replace `except:` with specific exception types + logging

### BLOCK-002: Missing Position Conflict Check in Paper Mode
**Original:** Issue #4 (HIGH)
**File(s):** `backend/services/core/execution_gateway.py:547-548`
**Problem:** Paper mode can simulate YES+NO on same market (impossible in reality)
**Dependencies:** Depends on STOP-001 being fixed (paper trading consistency)
**Fix:** Implement local position tracking for paper mode

### BLOCK-003: Price Revalidation Skipped in Paper Mode
**Original:** Issue #6 (HIGH)
**File(s):** `backend/services/core/execution_gateway.py:586-587`
**Problem:** Paper trades execute at stale prices from opportunity detection
**Dependencies:** None
**Fix:** Fetch fresh prices even in paper mode

### BLOCK-004: Market Close Time Check Fails Open
**Original:** Issue #7 (HIGH)
**File(s):** `backend/services/core/execution_gateway.py:615-657`
**Problem:** On API failure, trade proceeds without safety check
**Dependencies:** None
**Fix:** Return `False` on fetch failure to block execution

### BLOCK-005: Fee Type Confusion (Integer vs Float)
**Original:** Issue #8 (MEDIUM)
**File(s):** `backend/services/paper_trading.py:104, 111`
**Problem:** `calculate_fee()` returns int (cents) but context expects float
**Dependencies:** Depends on STOP-001 (same file, related issue)
**Fix:** Ensure consistent units throughout

### BLOCK-006: Database Balance in Dollars vs API in Cents
**Original:** Issue #13 (MEDIUM)
**File(s):** `backend/database/schema.sql:4-5` vs `backend/api/schemas.py:206`
**Problem:** Unit mismatch between database (dollars) and API (cents)
**Dependencies:** Depends on STOP-001 (unit standardization)
**Fix:** Standardize on cents throughout

### BLOCK-007: Incomplete TODO - Balance Not Fetched
**Original:** Issue #10 (MEDIUM)
**Problem:** Duplicate of STOP-002 - same TODO markers
**Status:** Merged with STOP-002

---

## Bucket 3: DEGRADED PERFORMANCE (Fix Soon)

These cause inefficiency. **Fix within 1 week.**

### PERF-001: Rate Limiter Too Conservative
**Original:** Issue #9 (MEDIUM)
**File(s):** `backend/services/kalshi_client.py:61-62`
**Problem:** Write limiter at 5/sec but Kalshi allows 10/sec
**Dependencies:** None
**Fix:** Change `max_requests=5` to `max_requests=10`

### PERF-002: Min 2-NO Strategy Documentation Gap
**Original:** Issue #11 (MEDIUM)
**File(s):** `backend/services/core/fee_calculator.py:450`
**Problem:** Strategy assumes mutually exclusive brackets but doesn't validate
**Dependencies:** None
**Fix:** Add validation that brackets are mutually exclusive

### PERF-003: Exception in Exception Handler
**Original:** Issue #12 (MEDIUM)
**File(s):** `backend/services/core/execution_gateway.py:328, 338`
**Problem:** Exception handlers could throw without handling
**Dependencies:** None
**Fix:** Add try/except around audit recording

---

## Bucket 4: TECHNICAL DEBT (Clean Up)

These make maintenance harder. **Fix opportunistically.**

### DEBT-001: Exception Swallowing in Multiple Services
**Original:** Issue #14 (LOW)
**File(s):** 80+ occurrences across codebase
**Problem:** Many `except Exception as e:` blocks that log but continue
**Fix:** Review each case individually

### DEBT-002: UTC vs Local Time Inconsistency
**Original:** Issue #15 (LOW)
**File(s):** `backend/services/btc_arb_scanner.py:709` and others
**Problem:** Mix of `datetime.now(timezone.utc)` and `datetime.utcnow()`
**Fix:** Standardize on `datetime.now(timezone.utc)`

### DEBT-003: Unused Imports
**Original:** Issue #16 (LOW)
**File(s):** Various
**Problem:** Potential unused imports
**Fix:** Run `ruff check` or `flake8` to identify

### DEBT-004: Missing Type Hints
**Original:** Issue #17 (LOW)
**File(s):** Various legacy services
**Problem:** Inconsistent type hinting
**Fix:** Add type hints to functions without them

---

## Dependency Graph

```
STOP-001 (Unit Confusion)
    ├── BLOCK-005 (Fee Type Confusion) - same file
    └── BLOCK-006 (DB/API Unit Mismatch) - unit standardization

STOP-002 (Hardcoded Balance)
    └── Merged: BLOCK-007 (TODO Balance)

STOP-003 (TOCTOU Race)
    └── Independent - can fix in parallel

BLOCK-002 (Paper Position Conflict)
    └── Depends on STOP-001 (paper trading consistency)

All other issues are independent and can be parallelized.
```

---

## Recommended Fix Order

### Phase 1: Unblock Live Trading (Day 1)
1. **STOP-001** - Fix unit confusion in paper_trading.py
2. **STOP-002** - Implement actual balance fetching in orchestrator
3. **STOP-003** - Add TOCTOU mitigation to execution gateway

### Phase 2: Production Ready (Day 2)
4. **BLOCK-001** - Replace bare except clauses
5. **BLOCK-002** - Implement paper mode position tracking
6. **BLOCK-003** - Add price revalidation to paper mode
7. **BLOCK-004** - Fix market close check to fail-closed
8. **BLOCK-005** - Ensure consistent fee units
9. **BLOCK-006** - Standardize DB/API units

### Phase 3: Performance (Week 1)
10. **PERF-001** - Adjust rate limiter
11. **PERF-002** - Add bracket validation
12. **PERF-003** - Fix exception handler

### Phase 4: Cleanup (Ongoing)
13. **DEBT-001 through DEBT-004** - Technical debt cleanup

---

## Metrics

| Metric | Count |
|--------|-------|
| Total issues | 17 |
| Blocking live trading | 3 |
| Blocking production | 6 (7 - 1 merged) |
| Performance issues | 3 |
| Technical debt | 4 |
| Files affected | 12 |
| Estimated fix time | 2-3 days for Buckets 1-2 |

---

## Validation Checklist

After fixes, verify:
- [ ] `python -c "from backend.main import app; print('OK')"` passes
- [ ] Paper trading calculates correct fees
- [ ] Balance fetched dynamically in orchestrator
- [ ] No bare except clauses in critical paths
- [ ] Paper mode enforces YES+NO constraint
- [ ] Market close check fails-closed
- [ ] Unit tests pass (if any)

---

**Next Step:** Execute fixes in dependency order, starting with STOP-001.
