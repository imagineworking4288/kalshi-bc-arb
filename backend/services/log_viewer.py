"""
Log Viewer Service - Tails logs with colors.
"""

import sys
import time
import signal
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.log_config import LOG_DIR, MAIN_LOG, SCANNER_LOG, API_LOG, ERROR_LOG, TRADE_LOG

class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    DEBUG = '\033[36m'
    INFO = '\033[32m'
    WARNING = '\033[33m'
    ERROR = '\033[31m'
    BTC = '\033[93m'
    WEATHER = '\033[96m'
    API = '\033[95m'
    HEADER = '\033[44m\033[97m'
    SEPARATOR = '\033[90m'


class LogViewer:
    """Real-time log viewer with filtering."""

    def __init__(self, log_file: Path, filter_source: str = None,
                 filter_level: str = None, filter_text: str = None):
        self.log_file = log_file
        self.filter_source = filter_source.lower() if filter_source else None
        self.filter_level = filter_level.upper() if filter_level else None
        self.filter_text = filter_text.lower() if filter_text else None
        self.running = True

    def colorize_line(self, line: str) -> str:
        if '| ERROR |' in line or '[ERROR]' in line:
            return f"{Colors.ERROR}{line}{Colors.RESET}"
        elif '| WARNING |' in line or '[WARNING]' in line:
            return f"{Colors.WARNING}{line}{Colors.RESET}"
        elif '| DEBUG |' in line:
            return f"{Colors.DIM}{line}{Colors.RESET}"
        elif 'btc_arb' in line.lower() or '[btc' in line.lower():
            return f"{Colors.BTC}{line}{Colors.RESET}"
        elif 'weather' in line.lower():
            return f"{Colors.WEATHER}{line}{Colors.RESET}"
        elif 'api' in line.lower():
            return f"{Colors.API}{line}{Colors.RESET}"
        return line

    def should_show(self, line: str) -> bool:
        line_lower = line.lower()
        if self.filter_source and self.filter_source not in line_lower:
            return False
        if self.filter_level and f'| {self.filter_level} |' not in line.upper():
            return False
        if self.filter_text and self.filter_text not in line_lower:
            return False
        return True

    def print_header(self):
        print('\033[2J\033[H', end='')
        print(f"{Colors.HEADER}{'=' * 80}{Colors.RESET}")
        print(f"{Colors.HEADER}{'KALSHI LOG VIEWER':^80}{Colors.RESET}")
        print(f"{Colors.HEADER}{'=' * 80}{Colors.RESET}")
        print(f"\n{Colors.DIM}Log: {self.log_file} | Ctrl+C to exit{Colors.RESET}\n")
        print(f"{Colors.SEPARATOR}{'─' * 80}{Colors.RESET}\n")

    def tail_file(self):
        self.print_header()

        try:
            with open(self.log_file, 'r') as f:
                f.seek(0, 2)  # Go to end

                while self.running:
                    line = f.readline()
                    if line:
                        if self.should_show(line):
                            print(self.colorize_line(line.rstrip()))
                    else:
                        time.sleep(0.1)
        except FileNotFoundError:
            print(f"{Colors.ERROR}Log file not found: {self.log_file}{Colors.RESET}")
            print(f"{Colors.DIM}Waiting for file to be created...{Colors.RESET}")
            while self.running and not self.log_file.exists():
                time.sleep(1)
            if self.running:
                self.tail_file()

    def stop(self):
        self.running = False


def main():
    parser = argparse.ArgumentParser(description='Kalshi Log Viewer')
    parser.add_argument('--file', '-f', choices=['all', 'api', 'scanner', 'errors', 'trades'],
                        default='all', help='Log file to tail')
    parser.add_argument('--source', '-s', help='Filter: btc, weather, api')
    parser.add_argument('--level', '-l', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--text', '-t', help='Filter by text')

    args = parser.parse_args()

    log_files = {
        'all': MAIN_LOG, 'api': API_LOG, 'scanner': SCANNER_LOG,
        'errors': ERROR_LOG, 'trades': TRADE_LOG
    }

    viewer = LogViewer(
        log_file=log_files.get(args.file, MAIN_LOG),
        filter_source=args.source,
        filter_level=args.level,
        filter_text=args.text
    )

    def signal_handler(sig, frame):
        viewer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        viewer.tail_file()
    except KeyboardInterrupt:
        viewer.stop()


if __name__ == "__main__":
    main()
