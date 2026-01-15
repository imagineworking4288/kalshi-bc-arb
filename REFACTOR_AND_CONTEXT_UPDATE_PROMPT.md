# Kalshi Trading System: Context Regeneration & Refactoring Prompt

**Purpose:** Analyze the actual codebase, update context documentation files, and create a prioritized refactoring plan based on confirmed bugs.

**Project Path:** `C:\Projects\kalshi-bc-arb`

---

## CRITICAL BUGS CONFIRMED (From Diagnostic)

These bugs MUST be addressed in the refactoring:

| Bug | Location | Impact |
|-----|----------|--------|
| **Fee Integration** | `weather_strategy.py:333-338` | Shows 2.04% edge when actual is -6.54%. Trades appear profitable but lose money after fees. |
| **No Partial Fill Rollback** | `batch_executor.py:255-290` | Zero rollback logic. Partial fills leave unhedged positions. |
| **Cache Stale on Partial** | `execution_gateway.py:294-297` | Cache only invalidates on `success=True`. Partial fills leave 30s stale data. |
| **Bracket Label Off-by-1** | `kalshi_models.py:265-273` | Open-ended brackets may display wrong temperature values. |

---

## PART 1: CONTEXT FILE REGENERATION

The context files (`context/INDEX.md`, `context/API.md`, `context/SCHEMAS.md`) may be outdated. Regenerate them by analyzing the actual codebase.

### Task 1.1: Regenerate INDEX.md

Analyze the project structure and create an accurate index:

```bash
# Get current project structure
find . -type f -name "*.py" | grep -v __pycache__ | grep -v ".venv" | sort

# Get all modules
find backend -type d -not -path "*__pycache__*" | sort

# Count lines per file
find backend -name "*.py" -not -path "*__pycache__*" -exec wc -l {} \; | sort -n
```

**Create `context/INDEX.md` with:**
1. Accurate file tree with descriptions
2. Module map showing actual dependencies
3. Entry points and how to run each component
4. Current state of each subsystem (working/broken/untested)

### Task 1.2: Regenerate API.md

For each Python file in `backend/`, extract:
- Class names and their purpose
- Public method signatures with parameters and return types
- Key constants and configuration

```bash
# Extract all class definitions
grep -rn "^class " backend/ --include="*.py" | head -100

# Extract all function definitions
grep -rn "^def \|^    def \|^    async def " backend/ --include="*.py" | head -200

# Find all API endpoints
grep -rn "@app\.\|@router\." backend/ --include="*.py"
```

**Create `context/API.md` with:**
1. Every class with its methods documented
2. Every REST endpoint with request/response schemas
3. Dependencies between components
4. Mark broken/untested methods

### Task 1.3: Regenerate SCHEMAS.md

Extract all data structures:

```bash
# Find all dataclasses
grep -rn "@dataclass" backend/ --include="*.py" -A 20

# Find all Pydantic models
grep -rn "class.*BaseModel\|class.*BaseSettings" backend/ --include="*.py" -A 20

# Find all TypedDicts
grep -rn "TypedDict\|Enum" backend/ --include="*.py" -A 10

# Find database schema
cat backend/database/schema.sql
```

**Create `context/SCHEMAS.md` with:**
1. All dataclasses with field types
2. All Pydantic models
3. Database table schemas
4. Enum definitions

---

## PART 2: DEEP CODEBASE ANALYSIS

Answer these questions by examining actual code:

### 2.1 Fee Calculation Flow

```bash
# Find all fee calculations
grep -rn "fee\|Fee" backend/services/ --include="*.py" | grep -v "test"

# Find where fees are calculated in weather strategy
grep -n "fee\|edge\|profit\|cost" backend/services/strategies/weather_strategy.py
```

**Questions:**
1. Where does WeatherStrategy calculate edge? Show the exact lines.
2. Does it call `FeeCalculator.analyze_weather_arbitrage()`?
3. Where does the 8.58% inflation come from?
4. What's the correct calculation flow?

**Output format:**
```markdown
## Fee Calculation Analysis

### Current (BROKEN) Flow in WeatherStrategy:
[Show exact code with line numbers]

### Where FeeCalculator EXISTS:
[Show analyze_weather_arbitrage signature and location]

### The Bug:
[Explain exactly why edge is inflated]

### Correct Flow Should Be:
[Describe fix]
```

### 2.2 Execution Flow Analysis

```bash
# Trace execution path
grep -rn "execute\|Execute" backend/services/core/ --include="*.py" | head -50

# Find batch_executor internals
grep -n "def \|async def " backend/services/core/batch_executor.py

# Find execution_gateway internals  
grep -n "def \|async def " backend/services/core/execution_gateway.py
```

**Questions:**
1. What is the call path from signal detection to order placement?
2. Where should rollback logic be added?
3. What happens when one leg of a batch fails?
4. Is execution synchronous or asynchronous?

**Output format:**
```markdown
## Execution Flow Analysis

### Current Call Path:
WeatherStrategy.scan() 
  → [what does it call?]
    → [next step]
      → KalshiClient.place_batch_orders()

### Batch Failure Handling:
[Show what currently happens]

### Gap: No Rollback
[Show where rollback should be added]

### Sync vs Async:
[Definitively answer: is KalshiClient sync or async?]
```

### 2.3 Position Management Analysis

```bash
# Find position tracking
grep -rn "position\|Position" backend/services/core/position_manager.py | head -30

# Find cache logic
grep -n "cache\|Cache\|invalidate" backend/services/core/position_manager.py
grep -n "cache\|Cache\|invalidate" backend/services/core/execution_gateway.py
```

**Questions:**
1. How does PositionManager cache positions?
2. What triggers cache invalidation?
3. Why doesn't partial fill invalidate cache?
4. Does `can_open_position()` exist and work?

**Output format:**
```markdown
## Position Management Analysis

### Cache Implementation:
[Show how positions are cached]

### Current Invalidation Logic:
[Show exact code at execution_gateway.py:294-297]

### The Bug:
[Explain why partial fills don't invalidate]

### Fix Required:
[Describe solution]
```

### 2.4 Bracket Label Analysis

```bash
# Find bracket_label implementation
grep -n "bracket_label\|floor_strike\|cap_strike" backend/models/kalshi_models.py

# Find where it's called
grep -rn "bracket_label" backend/ frontend/ --include="*.py" --include="*.ts" --include="*.tsx"
```

**Questions:**
1. What is the current `bracket_label()` implementation?
2. How does Kalshi encode open-ended brackets?
3. Is the off-by-1 bug confirmed?
4. What weather ticker prefixes exist?

---

## PART 3: GENERATE REFACTORING PLAN

Based on analysis, create `REFACTORING_PLAN.md`:

```markdown
# Kalshi Trading System Refactoring Plan

## Phase 0: Critical Bug Fixes (Do First - Before Any Trading)

### Fix 0.1: Fee Integration [CRITICAL]
**File:** backend/services/strategies/weather_strategy.py
**Lines:** 333-338
**Current Code:**
[paste broken code]

**Fixed Code:**
[paste corrected code]

**Test:**
[how to verify fix works]

### Fix 0.2: Partial Fill Rollback [CRITICAL]
**File:** backend/services/core/batch_executor.py
**Lines:** 255-290
**Current Code:**
[paste code showing no rollback]

**Fixed Code:**
[add rollback handler]

**Test:**
[how to verify]

### Fix 0.3: Cache Invalidation [HIGH]
**File:** backend/services/core/execution_gateway.py
**Lines:** 294-297
**Current Code:**
[paste conditional invalidation]

**Fixed Code:**
[unconditional invalidation]

**Test:**
[how to verify]

### Fix 0.4: Bracket Labels [MEDIUM]
**File:** backend/models/kalshi_models.py
**Lines:** 265-273
**Current Code:**
[paste current implementation]

**Fixed Code:**
[paste weather-aware implementation]

**Test:**
[how to verify]

## Phase 1: Core Infrastructure (After Bug Fixes)

### 1.1 Smart Arbitrage Executor
[description]

### 1.2 Unified Fee Calculation
[description]

### 1.3 Position Conflict Detection
[description]

## Phase 2: Enhanced Monitoring

### 2.1 Real-time P&L Tracking
### 2.2 Execution Audit Trail
### 2.3 Alert System

## Phase 3: Optimization

### 3.1 WebSocket for Real-time Data
### 3.2 Parallel Orderbook Fetching
### 3.3 Historical Backtesting
```

---

## PART 4: OUTPUT FILES

Generate these files in the project root:

### File 1: `context/INDEX.md` (Regenerated)
Complete project index with accurate file descriptions

### File 2: `context/API.md` (Regenerated)
All classes and methods with signatures

### File 3: `context/SCHEMAS.md` (Regenerated)
All data structures and database schemas

### File 4: `REFACTORING_PLAN.md` (New)
Prioritized refactoring with exact code fixes

### File 5: `CRITICAL_FIXES.md` (New)
Just the 4 critical bugs with copy-paste fixes

### File 6: `CODEBASE_HEALTH_REPORT.md` (New)
Current state assessment:
- What's working
- What's broken
- What's untested
- Dependencies map

---

## PART 5: VALIDATION QUERIES

Run these to confirm understanding:

### Fee Bug Validation
```python
# In Python REPL or script
from backend.services.core.fee_calculator import FeeCalculator, FeeType

# Simulate the broken calculation
yes_asks = [15, 20, 18, 22, 12, 13]  # Example brackets
gross_cost = sum(yes_asks)  # 100 cents
print(f"Gross cost: {gross_cost}¢")

# What WeatherStrategy SHOULD do:
fc = FeeCalculator()
analysis = fc.analyze_weather_arbitrage(yes_asks, [], FeeType.TAKER)
print(f"Net cost after fees: {analysis}")

# Compare to what it actually does
# [paste weather strategy's edge calculation]
```

### Execution Path Validation
```python
# Trace actual execution path
from backend.services.core.batch_executor import BatchExecutor
from backend.services.core.execution_gateway import ExecutionGateway

# Show method signatures
print(BatchExecutor.execute.__doc__)
print(ExecutionGateway.execute.__doc__)
```

---

## EXECUTION INSTRUCTIONS

1. **Run all bash commands** to gather actual code state
2. **Answer all questions** with evidence from code
3. **Generate all 6 output files** with accurate content
4. **Verify fixes** with the validation queries
5. **Commit** with message: "docs: regenerate context files, add refactoring plan"

**Estimated Time:** 45-60 minutes for complete analysis and file generation

---

## SUCCESS CRITERIA

After running this prompt, you should have:

- [ ] Updated `context/INDEX.md` matching actual project structure
- [ ] Updated `context/API.md` with all current methods
- [ ] Updated `context/SCHEMAS.md` with all data structures
- [ ] New `REFACTORING_PLAN.md` with prioritized fixes
- [ ] New `CRITICAL_FIXES.md` with copy-paste solutions
- [ ] New `CODEBASE_HEALTH_REPORT.md` with honest assessment
- [ ] Confirmed understanding of the 4 critical bugs
- [ ] Clear execution path documented
- [ ] All validation queries run successfully
