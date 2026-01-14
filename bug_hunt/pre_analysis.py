#!/usr/bin/env python3
"""
Pre-Analysis Script for Kalshi Bug Hunt
Run this BEFORE Phase 1 to generate initial indicators.

Usage:
    python pre_analysis.py > PRE_ANALYSIS_RESULTS.txt
"""

import subprocess
import re
import os
from pathlib import Path
from collections import defaultdict

# Configuration
PROJECT_ROOT = Path(".")
BACKEND_DIR = PROJECT_ROOT / "backend"

def run_cmd(cmd, capture=True):
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {e}"

def header(title):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

def find_pattern(pattern, description, directory="backend"):
    """Find pattern in codebase and report."""
    header(f"Searching: {description}")
    cmd = f'grep -rn "{pattern}" {directory}/ 2>/dev/null || true'
    output = run_cmd(cmd)
    if output.strip():
        print(output)
        return output.count('\n') + 1
    else:
        print("No matches found")
        return 0

def main():
    print("="*60)
    print(" KALSHI BUG HUNT PRE-ANALYSIS")
    print(" Generated for Phase 1 input")
    print("="*60)
    
    issues = defaultdict(list)
    
    # 1. Fee Calculation Patterns
    header("FEE CALCULATION PATTERNS")
    print("Looking for fee calculations that might be wrong...\n")
    
    # Check for the correct formula components
    cmd = 'grep -rn "0\\.07\\|fee.*calc\\|calculate.*fee" backend/ 2>/dev/null || true'
    output = run_cmd(cmd)
    print("Files with fee calculations:")
    print(output)
    
    # Check if (1-price) factor is present
    cmd = 'grep -rn "1.*-.*price\\|1 - price\\|(1-price)" backend/ 2>/dev/null || true'
    output2 = run_cmd(cmd)
    print("\nFiles with (1-price) factor (required for correct fee calc):")
    print(output2 if output2.strip() else "WARNING: (1-price) factor not found - possible bug!")
    
    # 2. Cents vs Dollars Confusion
    header("CENTS VS DOLLARS PATTERNS")
    print("Looking for potential decimal/cents confusion...\n")
    
    patterns = [
        ("price.*100\\|/ 100\\|\\* 100", "Multiplying/dividing by 100"),
        ("_cents.*_dollars\\|_dollars.*_cents", "Mixed cents/dollars variables"),
        ("price_cents.*price_dollars\\|price.*cents.*dollars", "Price unit conversions"),
    ]
    
    for pattern, desc in patterns:
        cmd = f'grep -rn "{pattern}" backend/ 2>/dev/null | head -20 || true'
        output = run_cmd(cmd)
        print(f"{desc}:")
        print(output if output.strip() else "  No matches")
        print()
    
    # 3. Error Handling Issues
    header("ERROR HANDLING GAPS")
    
    # Bare except
    cmd = 'grep -rn "except:$\\|except Exception:$" backend/ 2>/dev/null || true'
    output = run_cmd(cmd)
    print("Bare except clauses (swallow all errors):")
    print(output if output.strip() else "  None found (good!)")
    
    # pass in except
    cmd = 'grep -rn -A1 "except.*:" backend/ 2>/dev/null | grep -B1 "pass$" | grep -v "^--$" || true'
    output = run_cmd(cmd)
    print("\nExcept blocks with just 'pass' (silent failures):")
    print(output if output.strip() else "  None found (good!)")
    
    # 4. TODO/FIXME/HACK Comments
    header("INCOMPLETE CODE MARKERS")
    
    cmd = 'grep -rn "TODO\\|FIXME\\|HACK\\|XXX\\|BUG\\|BROKEN" backend/ 2>/dev/null || true'
    output = run_cmd(cmd)
    print("Developer markers indicating incomplete code:")
    print(output if output.strip() else "  None found")
    
    # 5. Async Issues
    header("ASYNC/AWAIT PATTERNS")
    
    # Missing await
    cmd = 'grep -rn "async def" backend/ 2>/dev/null | wc -l'
    async_count = run_cmd(cmd).strip()
    
    cmd = 'grep -rn "await " backend/ 2>/dev/null | wc -l'
    await_count = run_cmd(cmd).strip()
    
    print(f"async def declarations: {async_count}")
    print(f"await statements: {await_count}")
    
    # Functions that might need await
    cmd = 'grep -rn "\\(self\\.client\\.\\|kalshi_client\\.\\|self\\.db\\.\\)" backend/ 2>/dev/null | grep -v "await" | head -10 || true'
    output = run_cmd(cmd)
    print("\nPotential missing awaits (method calls without await):")
    print(output if output.strip() else "  None found")
    
    # 6. Import Analysis
    header("IMPORT ANALYSIS")
    
    # Count imports per module
    cmd = 'grep -rh "^from backend\\|^import backend" backend/ 2>/dev/null | sort | uniq -c | sort -rn | head -20'
    output = run_cmd(cmd)
    print("Most common internal imports (check for circular dependencies):")
    print(output)
    
    # 7. Duplicate Function Names
    header("POTENTIAL DUPLICATES")
    
    cmd = '''grep -rh "^def \\|^    def \\|^async def " backend/ 2>/dev/null | sed 's/def /\\ndef /g' | grep "def " | sed 's/(.*$//' | sed 's/.*def //' | sort | uniq -c | sort -rn | head -20'''
    output = run_cmd(cmd)
    print("Function names appearing multiple times:")
    print(output)
    
    # 8. Database Column Access
    header("DATABASE ACCESS PATTERNS")
    
    # Look for raw SQL
    cmd = 'grep -rn "SELECT\\|INSERT\\|UPDATE\\|DELETE" backend/ 2>/dev/null | grep -v ".pyc\\|__pycache__" | head -20 || true'
    output = run_cmd(cmd)
    print("Raw SQL statements (check for injection risks):")
    print(output if output.strip() else "  None found")
    
    # String concatenation in SQL
    cmd = 'grep -rn "f\".*SELECT\\|f\".*INSERT\\|+ \"SELECT\\|+ \"INSERT" backend/ 2>/dev/null || true'
    output = run_cmd(cmd)
    print("\nPotential SQL injection (string concatenation in queries):")
    print(output if output.strip() else "  None found (good!)")
    
    # 9. Kalshi-Specific Issues
    header("KALSHI API PATTERNS")
    
    # Position conflict checks
    cmd = 'grep -rn "YES.*NO\\|yes.*no\\|position.*side" backend/ 2>/dev/null | head -20 || true'
    output = run_cmd(cmd)
    print("Position/side handling (check for YES+NO conflict prevention):")
    print(output if output.strip() else "  Check manually - critical for Kalshi")
    
    # Rate limiting
    cmd = 'grep -rn "rate.*limit\\|RateLimiter\\|sleep\\|asyncio.sleep" backend/ 2>/dev/null | head -15 || true'
    output = run_cmd(cmd)
    print("\nRate limiting implementations:")
    print(output if output.strip() else "  None found - may need to add")
    
    # 10. File Statistics
    header("CODEBASE STATISTICS")
    
    cmd = 'find backend -name "*.py" | wc -l'
    py_count = run_cmd(cmd).strip()
    
    cmd = 'find backend -name "*.py" -exec wc -l {} + 2>/dev/null | tail -1'
    lines = run_cmd(cmd).strip()
    
    cmd = 'find backend -name "*.py" -exec grep -l "class " {} \\; 2>/dev/null | wc -l'
    class_count = run_cmd(cmd).strip()
    
    print(f"Python files: {py_count}")
    print(f"Total lines: {lines}")
    print(f"Files with classes: {class_count}")
    
    # Summary
    header("SUMMARY")
    print("""
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
""")

if __name__ == "__main__":
    main()
