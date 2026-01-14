# Kalshi Bug Hunt: Master Workflow

## Overview

This workflow systematically finds and fixes all bugs in your Kalshi arbitrage trading system.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   PHASE 1       │────►│   PHASE 2       │────►│   PHASE 3       │
│   Discovery     │     │   Analysis      │     │   Implementation│
│   (2-4 hours)   │     │   (1-2 hours)   │     │   (4-8 hours)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
     Claude Code             You + Claude            Claude Code
     finds bugs              triage bugs             fixes bugs
```

---

## Prerequisites

Before starting, ensure:

```bash
# Your project can import successfully
cd C:\Projects\kalshi-bc-arb
python -c "from backend.main import app; print('OK')"

# You have the project files referenced
ls backend/services/core/
ls backend/services/strategies/
```

---

## PHASE 1: Bug Discovery

### Step 1.1: Prepare Claude Code

Open Claude Code in your project directory:
```bash
cd C:\Projects\kalshi-bc-arb
# Open Claude Code (however you normally launch it)
```

### Step 1.2: Run Discovery Prompt

Copy the entire contents of `PHASE1_BUG_DISCOVERY_PROMPT.md` into Claude Code.

Wait for the full analysis (this may take 30-60 minutes).

### Step 1.3: Save Output

Save Claude Code's bug report to a file:
```
C:\Projects\kalshi-bc-arb\BUG_REPORT_RAW.md
```

---

## PHASE 2: Bug Analysis

### Step 2.1: Open Analysis Framework

Review `PHASE2_ANALYSIS_FRAMEWORK.md` alongside the bug report.

### Step 2.2: Categorize Each Bug

For each bug found, assign:
- **Bucket** (1-4)
- **Priority** within bucket
- **Dependencies** (what needs to be fixed first)

### Step 2.3: Create Prioritized List

Create a file `BUG_REPORT_PRIORITIZED.md` with bugs organized by:

```markdown
# BUCKET 1: CRITICAL (Fix Immediately)
## CRIT-001: [Bug Title]
...

# BUCKET 2: HIGH (Fix Before Production)  
## HIGH-001: [Bug Title]
...

# BUCKET 3: MEDIUM (Fix Soon)
## MED-001: [Bug Title]
...

# BUCKET 4: LOW (Cleanup)
## LOW-001: [Bug Title]
...
```

### Step 2.4: Identify Dependencies

Draw a dependency graph showing which fixes block others.

---

## PHASE 3: Implementation

### Step 3.1: Prepare Implementation Prompt

1. Open `PHASE3_IMPLEMENTATION_PROMPT.md`
2. Replace `[PASTE YOUR PHASE 1 + PHASE 2 ANALYSIS HERE]` with:
   - The full bug report from Phase 1
   - Your prioritization from Phase 2
   - Any specific notes about your system

### Step 3.2: Run Implementation in Claude Code

Copy the complete implementation prompt into Claude Code.

### Step 3.3: Review Each Fix

As Claude Code proposes fixes:
1. Review the change
2. Approve or request modifications
3. Run the validation command
4. Move to next fix

### Step 3.4: Final Validation

After all fixes:
```bash
# Full validation sequence
python -c "from backend.main import app; print('Imports OK')"
pytest backend/tests/ -v
python diagnose_infrastructure.py
python test_integration_startup.py
```

---

## Quick Reference Commands

### Find Bugs (run in project root)
```bash
# Fee calculations
grep -rn "0\.07\|fee.*calc\|calculate.*fee" backend/

# Potential race conditions
grep -rn "async def.*execute\|await.*get.*price" backend/

# Error handling gaps
grep -rn "except:\|except Exception:" backend/

# TODO/FIXME markers
grep -rn "TODO\|FIXME\|HACK\|XXX" backend/

# Unused imports (requires vulture)
pip install vulture
vulture backend/ --min-confidence 60
```

### Test Changes
```bash
# Quick import test
python -c "from backend.main import app; from backend.services.core.execution_gateway import ExecutionGateway; print('OK')"

# Fee calculator test
python -c "
from backend.services.core.fee_calculator import FeeCalculator
fc = FeeCalculator()
print('10 contracts @ 50c:', fc.calculate(10, 50), 'cents')
print('10 contracts @ 20c:', fc.calculate(10, 20), 'cents')
print('10 contracts @ 80c:', fc.calculate(10, 80), 'cents')
"

# Full diagnostic
python diagnose_infrastructure.py --fix
```

---

## Expected Timeline

| Phase | Duration | Who Does It |
|-------|----------|-------------|
| Phase 1 | 2-4 hours | Claude Code (automated) |
| Phase 2 | 1-2 hours | You (manual review) |
| Phase 3 | 4-8 hours | Claude Code (with your approval) |
| Validation | 1 hour | You (testing) |

**Total: 8-15 hours** for a complete audit and fix cycle.

---

## Success Criteria

The bug hunt is complete when:

- [ ] All CRITICAL issues are fixed
- [ ] All HIGH issues are fixed
- [ ] `python -c "from backend.main import app"` passes
- [ ] `pytest backend/tests/` passes with >80% success
- [ ] `python diagnose_infrastructure.py` shows all green
- [ ] Paper trading mode executes without errors
- [ ] Fee calculations are verified correct

---

## Post-Cleanup Tasks

After the bug hunt:

1. **Update documentation** - Reflect any API changes
2. **Add regression tests** - For each bug fixed
3. **Create monitoring** - For bugs that could recur
4. **Schedule next audit** - Recommend monthly

---

## Files in This Package

| File | Purpose |
|------|---------|
| `MASTER_WORKFLOW.md` | This file - orchestration guide |
| `PHASE1_BUG_DISCOVERY_PROMPT.md` | Prompt for finding bugs |
| `PHASE2_ANALYSIS_FRAMEWORK.md` | Framework for triaging bugs |
| `PHASE3_IMPLEMENTATION_PROMPT.md` | Prompt for fixing bugs |

---

## Getting Help

If you get stuck:
1. Post the specific error to this chat
2. Include the file and line number
3. Include what you've already tried

Good luck! 🎯
