"""
Run log viewer standalone.
Usage: python run_logs.py [options]

Options:
  --file, -f    Which log: all, api, scanner, errors, trades
  --source, -s  Filter by source: btc, weather, api
  --level, -l   Filter by level: DEBUG, INFO, WARNING, ERROR
  --text, -t    Filter by text content
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from backend.services.log_viewer import main
    main()
