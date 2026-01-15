# Codebase Diagnostic Prompt for Claude Code

**Purpose:** Analyze the Kalshi trading system codebase to answer critical questions before implementing Phase 1 fixes.

**Instructions:** Run this diagnostic and save results to `DIAGNOSTIC_RESULTS.md` in the project root.

---

## Run This Prompt in Claude Code

```
I need you to analyze this codebase and answer specific questions about the implementation. 
Generate a file called DIAGNOSTIC_RESULTS.md with your findings.

## Questions to Answer

### 1. ASYNC VS SYNC - Kalshi Client

Look at `backend/services/kalshi_client.py`:

- Is `KalshiClient` synchronous or asynchronous?
- What does `get_orderbook()` return? Show the method signature and return type.
- What does `place_batch_orders()` return? Show the method signature.
- Are there any `async def` methods in this file?

**Output format:**
```
## 1. Kalshi Client Analysis

**Client Type:** [SYNC / ASYNC]

**get_orderbook() signature:**
[paste actual code]

**get_orderbook() return structure:**
[describe what it returns based on code]

**place_batch_orders() signature:**
[paste actual code]

**Async methods found:** [YES/NO, list them]
```

### 2. ORDERBOOK STRUCTURE

Look at `backend/services/kalshi_client.py` and `backend/models/kalshi_models.py`:

- What structure does `get_orderbook()` return?
- Is there an `Orderbook` model? What fields does it have?
- How do other parts of the code access orderbook data?

Search for any usage of `orderbook` in the codebase:
```bash
grep -r "orderbook" backend/ --include="*.py" | head -30
```

**Output format:**
```
## 2. Orderbook Structure

**Raw API return format:**
[show structure]

**Orderbook model exists:** [YES/NO]
**Orderbook model fields:** [list them]

**How code accesses orderbook:**
[show examples from grep]
```

### 3. FEE CALCULATOR - Current Implementation

Look at `backend/services/core/fee_calculator.py`:

- Does `analyze_weather_arbitrage()` exist?
- What is its current signature?
- What does it return?
- Who calls this method? (search for usages)

```bash
grep -r "analyze_weather_arbitrage" backend/ --include="*.py"
```

**Output format:**
```
## 3. Fee Calculator Analysis

**Method exists:** [YES/NO]

**Current signature:**
[paste actual code]

**Current return structure:**
[describe]

**Callers found:**
[list files and line numbers]
```

### 4. POSITION MANAGER - Conflict Checking

Look at `backend/services/core/position_manager.py`:

- Does `can_open_position()` method exist?
- Does `has_position()` method exist?
- How does the system currently check for position conflicts?

**Output format:**
```
## 4. Position Manager Analysis

**can_open_position() exists:** [YES/NO]
**Signature:** [if exists]

**has_position() exists:** [YES/NO]
**Signature:** [if exists]

**Current conflict checking:**
[describe how it works]
```

### 5. CIRCUIT BREAKER - Integration Points

Look at `backend/services/core/circuit_breaker.py`:

- Does `can_trade()` method exist?
- Where is circuit breaker checked in the codebase?

```bash
grep -r "circuit_breaker" backend/ --include="*.py" | grep -v "test" | head -20
```

**Output format:**
```
## 5. Circuit Breaker Analysis

**can_trade() exists:** [YES/NO]
**Signature:** [if exists]

**Integration points found:**
[list where it's checked]
```

### 6. EXECUTION GATEWAY - Current Flow

Look at `backend/services/core/execution_gateway.py`:

- Does `ExecutionGateway` class exist?
- What methods does it have?
- Does it handle audit logging?
- Does it check circuit breaker?
- Does it check position conflicts?

**Output format:**
```
## 6. Execution Gateway Analysis

**Class exists:** [YES/NO]

**Methods:**
[list all public methods]

**Handles auditing:** [YES/NO, how]
**Checks circuit breaker:** [YES/NO, where]
**Checks position conflicts:** [YES/NO, where]
```

### 7. WEATHER STRATEGY - Current Implementation

Look at `backend/services/strategies/weather_strategy.py`:

- How does `scan()` method work?
- Does it call `analyze_weather_arbitrage()`?
- How does it currently handle fees?
- How does it execute trades?

**Output format:**
```
## 7. Weather Strategy Analysis

**scan() method exists:** [YES/NO]

**Calls analyze_weather_arbitrage:** [YES/NO, show the call]

**Current fee handling:**
[describe]

**Execution method:**
[how does it execute trades - what does it call]
```

### 8. RATE LIMITING - Current Implementation

Look at `backend/services/kalshi_client.py`:

- Is there a `RateLimiter` class?
- What are the configured limits?
- How is rate limiting applied to requests?

**Output format:**
```
## 8. Rate Limiting Analysis

**RateLimiter exists:** [YES/NO]
**Configured limits:** [requests per second]
**How it's applied:** [describe]
```

### 9. BRACKET LABEL - Current Implementation

Look at `backend/models/kalshi_models.py`:

- Find the `bracket_label()` method
- Paste the current implementation
- Find all places that call this method

```bash
grep -r "bracket_label" backend/ --include="*.py"
grep -r "bracket_label" frontend/ --include="*.ts" --include="*.tsx"
```

**Output format:**
```
## 9. Bracket Label Analysis

**Current implementation:**
[paste full method]

**Called from:**
[list all locations]
```

### 10. BATCH ORDER API - Expected Behavior

Look at `backend/services/kalshi_client.py` and any API documentation:

- What does `place_batch_orders()` expect as input?
- What does it return on success?
- What does it return on partial failure?
- Is there error handling for individual order failures?

Also check the project's API reference files for batch order documentation.

**Output format:**
```
## 10. Batch Order API Analysis

**Input format:**
[describe expected structure]

**Success response:**
[describe]

**Partial failure handling:**
[describe if documented]

**Error handling in code:**
[describe current implementation]
```

### 11. EXISTING TESTS - Coverage Check

Look in `backend/tests/`:

- Are there tests for `bracket_label()`?
- Are there tests for `analyze_weather_arbitrage()`?
- Are there tests for weather strategy?
- Are there tests for execution?

```bash
ls -la backend/tests/
grep -r "bracket_label\|analyze_weather\|WeatherStrategy" backend/tests/ --include="*.py"
```

**Output format:**
```
## 11. Test Coverage Analysis

**Test files found:**
[list]

**bracket_label tests:** [YES/NO, file]
**analyze_weather_arbitrage tests:** [YES/NO, file]
**WeatherStrategy tests:** [YES/NO, file]
**Execution tests:** [YES/NO, file]
```

### 12. WEATHER MARKET TICKERS - All Prefixes

Search the codebase for all weather-related ticker prefixes:

```bash
grep -r "KXHIGH\|KXLOW\|KXRAIN\|KXW" backend/ --include="*.py" | head -20
grep -r "weather" backend/config/ --include="*.py"
```

Check `backend/config/locations/registry.py` for defined weather markets.

**Output format:**
```
## 12. Weather Market Prefixes

**Prefixes found in code:**
[list all KXHIGH, KXLOW, KXRAIN, etc.]

**Defined in registry:**
[list from config]

**Series tickers:**
[list all weather series]
```

### 13. DATABASE SCHEMA - Relevant Tables

Look at `backend/database/schema.sql`:

- Does `execution_audit` table exist?
- What columns does it have?
- Are there any tables for tracking arbitrage executions?

**Output format:**
```
## 13. Database Schema Analysis

**execution_audit table:**
[paste CREATE TABLE statement if exists]

**Arbitrage tracking tables:**
[list any relevant tables]
```

### 14. PAPER TRADING - Current State

Look at `backend/services/paper_trading.py`:

- How does paper trading simulate fills?
- Does it simulate fees?
- Does it simulate FOK (Fill-Or-Kill)?

**Output format:**
```
## 14. Paper Trading Analysis

**Fill simulation:**
[describe how it works]

**Fee simulation:** [YES/NO, how]
**FOK simulation:** [YES/NO, how]
```

---

## Summary Section

After answering all questions, generate a summary:

```
## SUMMARY: Implementation Readiness

### Blocking Issues (Must Fix First)
[List any issues that would cause crashes]

### Integration Points Identified
- Kalshi Client: [SYNC/ASYNC]
- Execution Flow: [describe path from signal to order]
- Audit Logging: [where it happens]

### Existing Code to Reuse
[List methods/classes that already do what we need]

### Gaps to Fill
[List missing functionality]

### Recommended Implementation Order
1. [first thing to implement]
2. [second]
3. [etc.]
```

---

Save all of this analysis to `DIAGNOSTIC_RESULTS.md` in the project root.
```

---

## After Running Diagnostic

Once you have `DIAGNOSTIC_RESULTS.md`, upload it here and I will:

1. Update the Phase 1 implementation plan based on actual findings
2. Resolve the async/sync question definitively
3. Adjust code to match actual API structures
4. Identify what can be reused vs. what needs to be built

This diagnostic will answer approximately 80% of the "unknown" questions from the code review.
