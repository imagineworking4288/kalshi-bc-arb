# Phase 2: Bug Analysis Framework

After running Phase 1, use this framework to categorize and prioritize the findings.

---

## TRIAGE MATRIX

| Severity | Impact | Action Timeline |
|----------|--------|-----------------|
| **CRITICAL** | Could lose money, corrupt data, or break trading | Fix BEFORE any live trading |
| **HIGH** | Incorrect calculations, silent failures | Fix within 24 hours |
| **MEDIUM** | Performance issues, code smell | Fix within 1 week |
| **LOW** | Style, minor redundancies | Fix opportunistically |

---

## ISSUE CATEGORIZATION TEMPLATE

After Claude Code generates the bug report, organize findings into these buckets:

### Bucket 1: STOP TRADING (Fix Immediately)
Issues that could cause financial loss:
- [ ] Fee calculation errors
- [ ] Position conflict bugs (YES+NO same market)
- [ ] Decimal/cents confusion
- [ ] Race conditions in execution

### Bucket 2: BLOCK LIVE MODE (Fix Before Production)
Issues that break core functionality:
- [ ] API authentication problems
- [ ] Database schema mismatches
- [ ] Missing error handling on trades
- [ ] Incorrect arbitrage math

### Bucket 3: DEGRADED PERFORMANCE (Fix Soon)
Issues that cause inefficiency:
- [ ] Rate limit violations
- [ ] Stale cache problems
- [ ] Slow queries
- [ ] Memory leaks

### Bucket 4: TECHNICAL DEBT (Clean Up)
Issues that make maintenance harder:
- [ ] Duplicate code
- [ ] Dead code
- [ ] Unused imports
- [ ] Inconsistent patterns

---

## DEPENDENCY GRAPH

Some fixes depend on others. Map them:

```
Fee Calculator Fix
    └── Arbitrage Calculator depends on this
        └── All strategy signals depend on this
            └── Execution gateway depends on this
```

---

## VALIDATION CHECKLIST

After fixing each bug, verify:

- [ ] Unit test passes (if exists)
- [ ] Related integration test passes
- [ ] Paper trading mode works
- [ ] No regression in related features
- [ ] Code review by Claude

---

## METRICS TO TRACK

Before and after the cleanup:

| Metric | Before | After |
|--------|--------|-------|
| Total issues found | | |
| Critical issues | | |
| Lines of dead code removed | | |
| Duplicate functions consolidated | | |
| Test coverage % | | |
| Import errors on startup | 0 (already passing) | 0 |

---

## SAMPLE ANALYSIS OUTPUT

Here's what a properly triaged issue looks like:

```markdown
## CRITICAL-001: Fee Calculator Uses Wrong Formula

**Category**: Bucket 1 - STOP TRADING
**Dependencies**: Blocks Bucket 2 items (BLOCK-003, BLOCK-007)
**Files to Modify**: 
  - backend/services/core/fee_calculator.py
  - backend/services/arbitrage_calculator.py

**Current Code**:
```python
fee = contracts * price * 0.07  # WRONG - missing (1-price) factor
```

**Correct Code**:
```python
fee = contracts * price * (1 - price) * 0.07
```

**Validation**:
- [ ] Run: python -c "from backend.services.core.fee_calculator import FeeCalculator; fc = FeeCalculator(); print(fc.calculate(10, 50))"
- [ ] Expected: ~17 cents for 10 contracts at 50¢
- [ ] Run paper trade and verify fee display
```

---

## GO/NO-GO DECISION

After analysis, answer these questions:

1. **Are there any CRITICAL issues?**
   - YES → Do not proceed to live trading until fixed
   - NO → Proceed with caution

2. **How many issues touch the execution path?**
   - >5 → Full code review of execution_gateway.py needed
   - ≤5 → Targeted fixes acceptable

3. **Are there any issues that could cascade?**
   - YES → Fix in dependency order
   - NO → Can parallelize fixes

4. **Is the fee calculation correct everywhere?**
   - NO → This is a BLOCKER - fix first
   - YES → Proceed

---

## NEXT STEP

Once you've analyzed the Phase 1 output using this framework, proceed to Phase 3 to generate the implementation prompt.
