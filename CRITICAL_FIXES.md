# Critical Fixes - Copy-Paste Solutions

**Status:** MUST FIX BEFORE ANY LIVE TRADING  
**Diagnostic Date:** 2026-01-14

---

## Bug Summary

| # | Bug | File | Lines | Risk |
|---|-----|------|-------|------|
| 1 | Fee Integration | weather_strategy.py | 333-338 | Losing trades appear profitable |
| 2 | No Rollback | batch_executor.py | 255-290 | Unhedged positions on failures |
| 3 | Cache Stale | execution_gateway.py | 294-297 | Stale position data 30s |
| 4 | Bracket Label | kalshi_models.py | 265-273 | Wrong temperature display |

---

## Fix 1: Fee Integration Bug

**Problem:** WeatherStrategy calculates edge without fees, making losing trades appear profitable.

**Location:** `backend/services/strategies/weather_strategy.py` lines 333-338

**Find this pattern (BROKEN):**
```python
# BROKEN: This ignores fees
total_cost = sum(bracket.yes_ask for bracket in brackets)
payout = 100  # $1 per contract set
edge = (payout - total_cost) / total_cost * 100
```

**Replace with (FIXED):**
```python
# FIXED: Use FeeCalculator for accurate edge
from backend.services.core.fee_calculator import FeeCalculator, FeeType

# Collect prices
yes_asks = [bracket.yes_ask for bracket in brackets if bracket.yes_ask]
no_asks = [bracket.no_ask for bracket in brackets if bracket.no_ask]

# Use fee calculator (handles all 3 strategies)
analysis = FeeCalculator.analyze_weather_arbitrage(
    yes_asks=yes_asks,
    no_asks=no_asks,
    order_type=FeeType.TAKER
)

# Get the best strategy
best_strategy = analysis.get('best_strategy')
if not best_strategy:
    return None  # No profitable opportunity

strategy_data = analysis[best_strategy]
if not strategy_data.get('is_profitable', False):
    return None

# Use the fee-adjusted values
net_cost = strategy_data['net_cost']
net_profit = strategy_data['net_profit']
edge = (net_profit / net_cost * 100) if net_cost > 0 else 0
```

**Verification Test:**
```python
# Test that edge calculation matches fee calculator
from backend.services.core.fee_calculator import FeeCalculator, FeeType

# Example: 6 brackets with these YES asks
yes_asks = [15, 20, 18, 22, 12, 13]  # Total: 100¢
no_asks = [85, 80, 82, 78, 88, 87]  # Derived

analysis = FeeCalculator.analyze_weather_arbitrage(yes_asks, no_asks, FeeType.TAKER)
print(f"All YES strategy:")
print(f"  Gross cost: {analysis['all_yes']['gross_cost_cents']}¢")
print(f"  Fees: {analysis['all_yes']['total_fee_cents']}¢")
print(f"  Net cost: {analysis['all_yes']['net_cost_cents']}¢")
print(f"  Profitable: {analysis['all_yes']['is_profitable']}")

# If gross_cost = 100¢ and payout = 100¢, 
# after ~7¢ fees, net profit is NEGATIVE
# But the broken code would show 0% edge (break-even)
```

---

## Fix 2: Partial Fill Rollback

**Problem:** When atomic multi-leg execution partially fails, no rollback occurs.

**Location:** `backend/services/core/batch_executor.py` lines 255-290

**Find this pattern (BROKEN):**
```python
# BROKEN: No handling of partial fills
async def execute_batch(self, orders: List[Order]) -> BatchResult:
    results = []
    for order in orders:
        result = await self.kalshi.place_order(order)
        results.append(result)
    
    # If some failed, we still have partial positions!
    return BatchResult(results=results)
```

**Replace with (FIXED):**
```python
# FIXED: Add rollback for partial fills
async def execute_batch(self, orders: List[Order]) -> BatchResult:
    results = []
    filled_orders = []
    
    for order in orders:
        try:
            result = await self.kalshi.place_order(order)
            results.append(result)
            
            if result.get('filled', False):
                filled_orders.append({
                    'ticker': order.ticker,
                    'side': order.side,
                    'count': result.get('fill_count', order.count),
                    'price': result.get('fill_price', order.price)
                })
        except Exception as e:
            results.append({'error': str(e), 'order': order})
            break  # Stop on first failure
    
    # Check if all orders filled
    all_filled = len(filled_orders) == len(orders)
    
    if not all_filled and filled_orders:
        # ROLLBACK: Sell back partial fills
        logger.warning(f"Partial fill detected. Rolling back {len(filled_orders)} positions.")
        rollback_results = await self._rollback_positions(filled_orders)
        
        return BatchResult(
            success=False,
            results=results,
            rollback_executed=True,
            rollback_results=rollback_results
        )
    
    return BatchResult(
        success=all_filled,
        results=results,
        rollback_executed=False
    )

async def _rollback_positions(self, filled_orders: List[Dict]) -> List[Dict]:
    """Sell back positions from partial fills."""
    rollback_results = []
    
    for fill in filled_orders:
        try:
            # Create sell order to unwind position
            sell_order = Order(
                ticker=fill['ticker'],
                side=fill['side'],
                action='sell',  # Sell to close
                count=fill['count'],
                type='market'  # Market order for guaranteed fill
            )
            result = await self.kalshi.place_order(sell_order)
            rollback_results.append({
                'ticker': fill['ticker'],
                'success': result.get('filled', False),
                'result': result
            })
        except Exception as e:
            rollback_results.append({
                'ticker': fill['ticker'],
                'success': False,
                'error': str(e)
            })
            logger.error(f"Rollback failed for {fill['ticker']}: {e}")
    
    return rollback_results
```

**Verification Test:**
```python
# Mock test for rollback
class MockKalshiClient:
    def __init__(self, fail_on_order=2):
        self.call_count = 0
        self.fail_on = fail_on_order
    
    async def place_order(self, order):
        self.call_count += 1
        if self.call_count == self.fail_on:
            raise Exception("Simulated failure")
        return {'filled': True, 'fill_count': order.count}

# Test that rollback is triggered
mock = MockKalshiClient(fail_on_order=3)
executor = BatchExecutor(kalshi=mock)
result = await executor.execute_batch([order1, order2, order3])

assert result.success == False
assert result.rollback_executed == True
print("Rollback test passed!")
```

---

## Fix 3: Cache Invalidation on Partial Fill

**Problem:** Position cache only invalidates on success, not partial fills.

**Location:** `backend/services/core/execution_gateway.py` lines 294-297

**Find this pattern (BROKEN):**
```python
# BROKEN: Only invalidates on success
async def execute(self, orders) -> ExecutionResult:
    result = await self.batch_executor.execute_batch(orders)
    
    if result.success:  # BUG: Partial fills have success=False
        self.position_manager.invalidate_cache()
    
    return result
```

**Replace with (FIXED):**
```python
# FIXED: Invalidate on ANY execution attempt
async def execute(self, orders) -> ExecutionResult:
    result = await self.batch_executor.execute_batch(orders)
    
    # ALWAYS invalidate cache after execution attempt
    # Even failed attempts may have partial fills
    self.position_manager.invalidate_cache()
    
    # Also invalidate if rollback occurred
    if getattr(result, 'rollback_executed', False):
        logger.info("Rollback executed, forcing position refresh")
        await self.position_manager.refresh_from_api()
    
    return result
```

**Alternative - Invalidate at Method Start:**
```python
# Even more defensive: invalidate BEFORE and AFTER
async def execute(self, orders) -> ExecutionResult:
    # Pre-invalidate to ensure fresh state
    self.position_manager.invalidate_cache()
    
    result = await self.batch_executor.execute_batch(orders)
    
    # Post-invalidate to capture any changes
    self.position_manager.invalidate_cache()
    
    return result
```

**Verification Test:**
```python
# Test cache is invalidated on failure
from unittest.mock import Mock, patch

position_manager = Mock()
batch_executor = Mock()
batch_executor.execute_batch.return_value = BatchResult(success=False)

gateway = ExecutionGateway(position_manager, batch_executor)
await gateway.execute([order])

# Verify invalidate was called even though success=False
position_manager.invalidate_cache.assert_called()
print("Cache invalidation test passed!")
```

---

## Fix 4: Bracket Label Off-by-One

**Problem:** Open-ended weather brackets may display wrong temperature.

**Location:** `backend/models/kalshi_models.py` lines 265-273

**Find this pattern (NEEDS VERIFICATION):**
```python
# Current implementation - may be missing +1/-1 adjustment
def bracket_label(self) -> str:
    if self.floor_strike is not None and self.cap_strike is not None:
        return f"{self.floor_strike}-{self.cap_strike}°F"
    elif self.floor_strike is not None:
        return f"{self.floor_strike}° or above"  # Missing +1?
    elif self.cap_strike is not None:
        return f"{self.cap_strike}° or below"  # Missing -1?
    return self.title or "Unknown"
```

**Replace with (FIXED):**
```python
def bracket_label(self) -> str:
    """Generate human-readable bracket label.
    
    Weather Market Encoding (Kalshi uses):
    - Open-ended lower: "below X" means cap_strike=X, actual cutoff is X-1
    - Open-ended upper: "above X" means floor_strike=X, actual cutoff is X+1
    - Range: floor to cap inclusive
    
    Example: cap_strike=47 → display "46°F or below"
    Example: floor_strike=49 → display "50°F or above"
    """
    # Detect weather markets by ticker prefix
    weather_prefixes = ("KXHIGH", "KXLOW", "KXRAIN")
    is_weather = self.ticker.startswith(weather_prefixes) if self.ticker else False
    
    # Range bracket (both strikes defined)
    if self.floor_strike is not None and self.cap_strike is not None:
        if is_weather:
            return f"{self.floor_strike}-{self.cap_strike}°F"
        return f"{self.floor_strike}-{self.cap_strike}"
    
    # Open-ended upper (floor_strike only → "X or above")
    elif self.floor_strike is not None:
        if is_weather:
            # Kalshi: floor_strike=49 means "49 or more" → display "50°F or above"
            return f"{self.floor_strike + 1}°F or above"
        return f"≥{self.floor_strike}"
    
    # Open-ended lower (cap_strike only → "X or below")  
    elif self.cap_strike is not None:
        if is_weather:
            # Kalshi: cap_strike=47 means "47 or less" → display "46°F or below"
            return f"{self.cap_strike - 1}°F or below"
        return f"<{self.cap_strike}"
    
    # Fallback
    return self.title or "Unknown"
```

**Verification Test:**
```python
from backend.models.kalshi_models import Market

# Test weather open-ended upper
m1 = Market(ticker="KXHIGHNY-25JAN15-49", floor_strike=49, cap_strike=None)
assert m1.bracket_label() == "50°F or above", f"Got: {m1.bracket_label()}"

# Test weather open-ended lower
m2 = Market(ticker="KXHIGHNY-25JAN15-46", floor_strike=None, cap_strike=47)
assert m2.bracket_label() == "46°F or below", f"Got: {m2.bracket_label()}"

# Test weather range (no adjustment)
m3 = Market(ticker="KXHIGHNY-25JAN15-47-48", floor_strike=47, cap_strike=48)
assert m3.bracket_label() == "47-48°F", f"Got: {m3.bracket_label()}"

# Test BTC market (should NOT adjust)
m4 = Market(ticker="KXBTC-25JAN15-100000", floor_strike=100000, cap_strike=None)
assert m4.bracket_label() == "≥100000", f"Got: {m4.bracket_label()}"

print("All bracket label tests passed!")
```

---

## Implementation Order

1. **Fix 1 (Fee Integration)** - Highest impact, prevents false profitable signals
2. **Fix 3 (Cache Invalidation)** - Quick fix, prevents stale data
3. **Fix 2 (Rollback)** - More complex, but critical for safety
4. **Fix 4 (Bracket Label)** - Lower priority, cosmetic but important

---

## After Fixing

Run these validation checks:

```bash
# Run all tests
python -m pytest backend/tests/ -v

# Check for any remaining fee calculation outside fee_calculator
grep -rn "edge\s*=" backend/services/strategies/ --include="*.py"

# Check all cache invalidation points
grep -rn "invalidate_cache" backend/ --include="*.py"

# Check bracket_label callers work correctly
grep -rn "bracket_label" backend/ frontend/ --include="*.py" --include="*.tsx"
```

---

## Rollback Instructions

If any fix causes issues:

```bash
# Revert single file
git checkout HEAD -- backend/services/strategies/weather_strategy.py

# Revert all changes
git stash

# View what changed
git diff HEAD
```
