# Phase 1: Comprehensive Bug Discovery Prompt for Claude Code

**Copy this entire prompt to Claude Code to begin the analysis.**

---

## SYSTEM CONTEXT

You are analyzing a Kalshi prediction market arbitrage trading system. The codebase has:
- 48 Python files in `backend/services/`
- React/TypeScript frontend
- SQLite database
- FastAPI backend on port 8001
- Paper trading + live trading modes

**CRITICAL CONSTRAINT**: Kalshi does NOT allow holding YES and NO on the same market simultaneously. Buying YES auto-sells any NO position (and vice versa).

---

## YOUR MISSION

Perform an exhaustive code audit. Search for bugs, errors, redundancies, and architectural issues. Output a structured report.

---

## ANALYSIS CATEGORIES

### 1. CRITICAL BUGS (Could Lose Money)

Search for:
- **Fee calculation errors**: Verify formula `0.07 × contracts × price × (1-price)` is correctly implemented everywhere
- **Off-by-one errors**: Temperature brackets (known issue: off by 1°F), array indexing, pagination
- **Race conditions / TOCTOU**: Price checks that could be stale by execution time
- **Position conflicts**: Code that might try to hold YES+NO simultaneously
- **Decimal/cents confusion**: Mixing dollars and cents (price in cents but using as dollars)
- **Integer division bugs**: Python 3 uses true division but check for truncation issues
- **Async/await missing**: Functions that should be async but aren't, or missing awaits

### 2. API INTEGRATION BUGS

Search for:
- **Wrong endpoints**: Compare code against Kalshi API reference
- **Missing authentication**: Endpoints that require auth but don't include headers
- **Rate limit violations**: Burst patterns that could exceed 20/sec read, 10/sec write
- **Query parameter errors**: Parameters in signature (should be stripped before signing)
- **Response parsing errors**: Fields that might be null but aren't handled
- **Orderbook interpretation**: YES bid at X = NO ask at (100-X) - verify this is correct

### 3. DATABASE ISSUES

Search for:
- **Schema mismatches**: Code expecting columns that don't exist
- **SQL injection risks**: String concatenation instead of parameterized queries
- **Transaction boundaries**: Operations that should be atomic but aren't
- **Stale data**: Cached data used after it should have expired
- **Missing indexes**: Slow queries on frequently-accessed columns

### 4. REDUNDANCIES

Search for:
- **Duplicate functions**: Same logic implemented in multiple places
- **Unused imports**: Imported but never used
- **Dead code**: Functions/classes never called
- **Duplicate constants**: Same values defined in multiple files
- **Overlapping services**: Multiple services doing the same job

### 5. TYPE SAFETY ISSUES

Search for:
- **TypedDict mismatches**: Python types not matching actual data
- **Optional fields**: Fields that could be None but aren't handled
- **Type coercion bugs**: int(string) that could fail
- **Pydantic validation gaps**: Models missing validators

### 6. ERROR HANDLING GAPS

Search for:
- **Bare except clauses**: `except:` or `except Exception:` swallowing errors
- **Silent failures**: Errors caught but not logged or raised
- **Missing try/catch**: API calls without error handling
- **Inconsistent error responses**: Different error formats across endpoints

### 7. BUSINESS LOGIC ERRORS

Search for:
- **Arbitrage calculation bugs**: Sum of brackets not equaling expected value
- **Profit calculation errors**: Not accounting for fees, slippage
- **Kelly criterion bugs**: Position sizing that could over-allocate
- **Settlement logic**: Incorrect handling of market settlement
- **Time zone issues**: UTC vs local time confusion

### 8. SECURITY ISSUES

Search for:
- **Hardcoded secrets**: API keys, passwords in code
- **Logging sensitive data**: Passwords, keys in logs
- **File path vulnerabilities**: User input used in file paths
- **CORS issues**: Overly permissive CORS settings

---

## OUTPUT FORMAT

For each issue found, provide:

```markdown
### [CATEGORY] Issue #N: Brief Title

**Severity**: CRITICAL | HIGH | MEDIUM | LOW
**File(s)**: path/to/file.py:line_number
**Description**: What's wrong
**Evidence**: Code snippet showing the bug
**Impact**: What could go wrong
**Fix**: How to fix it
```

---

## FILES TO ANALYZE

Start with these high-priority files:

### Core Trading (analyze first)
```
backend/services/core/execution_gateway.py
backend/services/core/fee_calculator.py
backend/services/core/batch_executor.py
backend/services/kalshi_client.py
backend/services/paper_trading.py
backend/services/trade_executor.py
```

### Arbitrage Detection
```
backend/services/arbitrage_calculator.py
backend/services/arbitrage_detector.py
backend/services/btc_arb_scanner.py
backend/services/weather_arb_scanner.py
backend/services/strategies/weather_strategy.py
backend/services/strategies/btc_arb_strategy.py
```

### Data Models
```
backend/models/kalshi_models.py
backend/models/nws_models.py
backend/models/types.py
backend/models/execution_models.py
```

### Configuration
```
backend/config/__init__.py
backend/config/fees.py
backend/database/schema.sql
```

### API Routes
```
backend/api/routes.py
backend/api/prediction_routes.py
```

---

## SPECIFIC KNOWN ISSUES TO VERIFY

1. **Bracket labeling off by 1°F** - Find where temperature brackets are labeled and verify floor_strike/cap_strike handling
2. **Fee integration gaps** - Find all profit calculations and verify fees are subtracted
3. **TOCTOU in execution** - Find time gap between price check and order placement
4. **Rate limiting on NWS API** - Verify circuit breaker implementation

---

## COMMANDS TO RUN

Execute these to gather information:

```bash
# Find all fee calculations
grep -rn "calculate.*fee\|fee.*calc\|0\.07\|0\.035" backend/

# Find all price-to-cents conversions
grep -rn "* 100\|/ 100\|_cents\|_dollars" backend/

# Find potential race conditions
grep -rn "async def.*execute\|await.*get.*price\|sleep" backend/

# Find error handling patterns
grep -rn "except:\|except Exception\|pass$" backend/

# Find TODO/FIXME/HACK comments
grep -rn "TODO\|FIXME\|HACK\|XXX\|BUG" backend/

# List all imports to find duplicates
grep -rn "^from\|^import" backend/ | sort | uniq -c | sort -rn | head -50

# Find unused functions (basic check)
grep -rn "def " backend/ | cut -d: -f2 | sed 's/def //' | sed 's/(.*$//' | sort | uniq > /tmp/funcs.txt
```

---

============================================================
 KALSHI BUG HUNT PRE-ANALYSIS
 Generated for Phase 1 input
============================================================

============================================================
 FEE CALCULATION PATTERNS
============================================================
Looking for fee calculations that might be wrong...

Files with fee calculations:
The system cannot find the path specified.
'true' is not recognized as an internal or external command,
operable program or batch file.


Files with (1-price) factor (required for correct fee calc):
The system cannot find the path specified.
'true' is not recognized as an internal or external command,
operable program or batch file.


============================================================
 CENTS VS DOLLARS PATTERNS
============================================================
Looking for potential decimal/cents confusion...

Multiplying/dividing by 100:
The system cannot find the path specified.


Mixed cents/dollars variables:
The system cannot find the path specified.


Price unit conversions:
The system cannot find the path specified.



============================================================
 ERROR HANDLING GAPS
============================================================
Bare except clauses (swallow all errors):
The system cannot find the path specified.
'true' is not recognized as an internal or external command,
operable program or batch file.


Except blocks with just 'pass' (silent failures):
The system cannot find the path specified.


============================================================
 INCOMPLETE CODE MARKERS
============================================================
Developer markers indicating incomplete code:
The system cannot find the path specified.
'true' is not recognized as an internal or external command,
operable program or batch file.


============================================================
 ASYNC/AWAIT PATTERNS
============================================================
async def declarations: The system cannot find the path specified.
await statements: The system cannot find the path specified.

Potential missing awaits (method calls without await):
The system cannot find the path specified.


============================================================
 IMPORT ANALYSIS
============================================================
Most common internal imports (check for circular dependencies):
The system cannot find the path specified.


============================================================
 POTENTIAL DUPLICATES
============================================================
Function names appearing multiple times:
The system cannot find the path specified.


============================================================
 DATABASE ACCESS PATTERNS
============================================================
Raw SQL statements (check for injection risks):
The system cannot find the path specified.


Potential SQL injection (string concatenation in queries):
'grep' is not recognized as an internal or external command,
operable program or batch file.


============================================================
 KALSHI API PATTERNS
============================================================
Position/side handling (check for YES+NO conflict prevention):
The system cannot find the path specified.


Rate limiting implementations:
The system cannot find the path specified.


============================================================
 CODEBASE STATISTICS
============================================================
Python files: Access denied - BACKEND
File not found - -NAME
'wc' is not recognized as an internal or external command,
operable program or batch file.
Total lines: The system cannot find the path specified.
Files with classes: The system cannot find the path specified.

============================================================
 SUMMARY
============================================================

Pre-analysis complete. Review the output above for:

1. FEE CALCULATIONS - Verify (1-price) factor is present
2. CENTS/DOLLARS - Check unit conversions are consistent  
3. ERROR HANDLING - Fix bare except clauses
4. TODO MARKERS - Complete or remove incomplete code
5. ASYNC ISSUES - Ensure all async calls are awaited
6. DUPLICATES - Consolidate duplicate functions
7. DATABASE - Check for SQL injection risks
8. KALSHI API - Verify position conflict prevention

Feed this output to Claude Code with the Phase 1 prompt for detailed analysis.

## BEGIN ANALYSIS

Start by reading the project structure, then systematically analyze each file category. Be thorough - this codebase will handle real money.

Output your complete findings in a structured markdown report.
