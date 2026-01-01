"""
Run scanner service standalone.
Usage: python run_scanners.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from backend.services.scanner_service import main
    main()
