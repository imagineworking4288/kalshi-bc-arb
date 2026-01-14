# Phase 3: Massive Implementation Prompt for Claude Code

**Use this prompt AFTER completing Phase 1 and Phase 2 analysis.**

Replace the `[PASTE BUG REPORT HERE]` section with your analyzed findings.

---

## SYSTEM CONTEXT

You are implementing fixes for a Kalshi prediction market arbitrage trading system. The codebase uses:
- Python 3.11+ with FastAPI backend
- React 18 + TypeScript frontend
- SQLite with aiosqlite
- Pydantic for data validation

**CRITICAL CONSTRAINT**: Kalshi does NOT allow holding YES and NO on the same market simultaneously.

---

## YOUR MISSION

Fix all identified bugs, remove redundancies, and improve code quality. Work systematically through each issue.

---

## BUG REPORT TO FIX

[PASTE YOUR PHASE 1 + PHASE 2 ANALYSIS HERE]

---

## IMPLEMENTATION RULES

### Rule 1: Fix in Order
Process issues in this order:
1. CRITICAL (fee calculations, position conflicts)
2. HIGH (API bugs, data handling)
3. MEDIUM (performance, error handling)
4. LOW (cleanup, style)

### Rule 2: Preserve Functionality
- Run existing tests before and after each fix
- Do not change public interfaces without updating all callers
- Maintain backwards compatibility with existing database

### Rule 3: One Fix at a Time
For each issue:
1. Show the current buggy code
2. Explain what's wrong
3. Show the fixed code
4. Explain why the fix is correct
5. Note any related files that need updates

### Rule 4: Test Each Fix
After each fix, provide a test command:
```bash
# Example
python -c "from backend.services.core.fee_calculator import FeeCalculator; ..."
```

### Rule 5: Document Changes
Add/update docstrings explaining the fix:
```python
def calculate_fee(contracts: int, price_cents: int) -> int:
    """
    Calculate Kalshi trading fee.
    
    Formula: 0.07 × contracts × (price/100) × (1 - price/100) × 100
    
    Fixed 2025-01-14: Was missing (1-price) factor causing underestimated fees.
    """
```

---

## SPECIFIC FIX TEMPLATES

### Template: Fee Calculation Fix

If fee calculation is incorrect:

```python
# backend/services/core/fee_calculator.py

# BEFORE (buggy)
def calculate(self, contracts: int, price_cents: int) -> int:
    return int(contracts * price_cents * 0.07)  # WRONG

# AFTER (fixed)
def calculate(self, contracts: int, price_cents: int) -> int:
    """
    Kalshi fee formula: 0.07 × contracts × price × (1-price)
    where price is in decimal form (0.0-1.0)
    """
    price_decimal = price_cents / 100
    fee = 0.07 * contracts * price_decimal * (1 - price_decimal) * 100
    return int(fee + 0.5)  # Round to nearest cent
```

### Template: Race Condition Fix

If there's a TOCTOU bug:

```python
# BEFORE (buggy)
async def execute(self, opportunity):
    price = await self.get_price(opportunity.ticker)  # Time T1
    # ... other code ...
    await self.place_order(opportunity.ticker, price)  # Time T2 - price may have changed!

# AFTER (fixed)
async def execute(self, opportunity):
    # Get price and place order atomically
    current_price = await self.get_price(opportunity.ticker)
    
    # Validate price hasn't moved beyond slippage tolerance
    if abs(current_price - opportunity.expected_price) > self.max_slippage_cents:
        raise PriceMovedError(f"Price moved from {opportunity.expected_price} to {current_price}")
    
    # Use current_price, not stale opportunity.expected_price
    await self.place_order(opportunity.ticker, current_price)
```

### Template: Position Conflict Prevention

```python
# backend/services/core/position_manager.py

async def can_open_position(self, ticker: str, side: str) -> tuple[bool, str]:
    """
    Check Kalshi constraint: Cannot hold YES and NO simultaneously.
    
    Returns: (can_open, reason)
    """
    existing = await self.get_position(ticker)
    
    if existing is None:
        return True, "No existing position"
    
    if existing.side == side:
        return True, "Same side - will add to position"
    
    # CRITICAL: Kalshi auto-sells opposite position
    return False, f"Cannot open {side} - already holding {existing.contracts} {existing.side}"
```

### Template: Off-by-One Fix

For temperature bracket labeling:

```python
# BEFORE (buggy)
def bracket_label(self) -> str:
    return f"{self.floor_strike}-{self.cap_strike}°F"  # Off by 1?

# AFTER (fixed)
def bracket_label(self) -> str:
    """
    Kalshi weather brackets use inclusive bounds.
    Example: floor_strike=62, cap_strike=63 means "62-63°F" (includes both 62 and 63)
    
    Fixed 2025-01-14: Verified against Kalshi UI - floor_strike and cap_strike are
    already the correct values, no adjustment needed.
    """
    if self.floor_strike is None:
        return f"≤{self.cap_strike}°F"
    if self.cap_strike is None:
        return f"≥{self.floor_strike}°F"
    return f"{self.floor_strike}-{self.cap_strike}°F"
```

### Template: Duplicate Code Consolidation

```python
# BEFORE (duplicated in multiple files)
# file1.py
def calculate_profit(cost, payout):
    return payout - cost

# file2.py  
def calc_profit(c, p):
    return p - c

# AFTER (consolidated)
# backend/utils/calculations.py
def calculate_profit(cost_cents: int, payout_cents: int) -> int:
    """Calculate profit from an arbitrage opportunity."""
    return payout_cents - cost_cents

# Update all callers to use this single function
```

---

## CLEANUP CHECKLIST

After fixing all bugs, perform these cleanups:

### 1. Remove Dead Code
```bash
# Find potentially unused functions
vulture backend/ --min-confidence 80
```

### 2. Remove Unused Imports
```bash
# Auto-fix with autoflake
autoflake --in-place --remove-all-unused-imports --recursive backend/
```

### 3. Consolidate Duplicates
- Merge duplicate fee calculators
- Merge duplicate price converters
- Create shared utility modules

### 4. Update Imports
After moving/consolidating code:
```python
# Update __init__.py exports
# Update all import statements
# Run: python -c "from backend.main import app" to verify
```

---

## VALIDATION SEQUENCE

After all fixes are complete:

```bash
# 1. Verify imports
python -c "from backend.main import app; print('Imports OK')"

# 2. Run existing tests
pytest backend/tests/ -v

# 3. Start server and verify health
uvicorn backend.main:app --port 8099 &
sleep 5
curl http://localhost:8099/health
kill %1

# 4. Run integration test
python test_integration_startup.py

# 5. Verify fee calculations
python -c "
from backend.services.core.fee_calculator import FeeCalculator
fc = FeeCalculator()
# 10 contracts at 50 cents should be ~17.5 cents fee
result = fc.calculate(10, 50)
print(f'Fee for 10@50c: {result} cents')
assert 15 <= result <= 20, f'Fee calculation wrong: {result}'
print('Fee calculation CORRECT')
"

# 6. Run diagnostic
python diagnose_infrastructure.py
```

---

## DELIVERABLES

After implementation, provide:

1. **Summary of changes** - List each file modified and why
2. **Test results** - Output from validation sequence
3. **Remaining issues** - Any issues that couldn't be fixed and why
4. **Recommendations** - Suggestions for further improvements

---

## BEGIN IMPLEMENTATION

Start with the highest priority (CRITICAL) issues and work down. Show your work for each fix.
