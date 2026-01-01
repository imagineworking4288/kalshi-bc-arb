"""
Standalone Scanner Service

Runs all arbitrage scanners in a separate process.
Writes results to SQLite database for API to read.
"""

import asyncio
import signal
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Setup logging FIRST
from backend.services.log_config import setup_logging
setup_logging("scanner")

logger = logging.getLogger("scanner")

from backend.services.kalshi_client import KalshiClient
from backend.services.btc_arb_scanner import BTCArbitrageScanner
from backend.services.weather_arb_scanner import WeatherArbScanner
from backend.services.scanner_db import ScannerDatabase

class ScannerService:
    """Unified scanner service that runs all scanners."""

    def __init__(self):
        self.running = False
        self.db = ScannerDatabase()

        # Initialize Kalshi client
        self.kalshi = KalshiClient()

        # Initialize scanners
        self.btc_scanner = BTCArbitrageScanner(self.kalshi)
        self.weather_scanner = WeatherArbScanner(self.kalshi)

        # Scanner intervals
        self.btc_interval = 2.0       # BTC: every 2s (fast moving)
        self.weather_interval = 30.0  # Weather: every 30s (slow moving)

        logger.info("=" * 60)
        logger.info("SCANNER SERVICE INITIALIZED")
        logger.info("=" * 60)
        logger.info(f"  BTC Scanner:     Every {self.btc_interval}s")
        logger.info(f"  Weather Scanner: Every {self.weather_interval}s")
        logger.info(f"  Weather Cities:  {len(self.weather_scanner.locations)} × 2 types = {len(self.weather_scanner.locations) * 2} series")
        logger.info("=" * 60)

    async def run_btc_scanner(self):
        """Run BTC scanner loop."""
        logger.info("[BTC] Scanner started")

        while self.running:
            try:
                result = await self.btc_scanner.scan_once()
                self.db.save_scanner_result("btc", result)
            except Exception as e:
                logger.error(f"[BTC] Scan error: {e}")

            await asyncio.sleep(self.btc_interval)

        logger.info("[BTC] Scanner stopped")

    async def run_weather_scanner(self):
        """Run weather scanner loop."""
        logger.info("[WEATHER] Scanner started")

        while self.running:
            try:
                result = await self.weather_scanner.scan_once()
                self.db.save_scanner_result("weather", result)
            except Exception as e:
                logger.error(f"[WEATHER] Scan error: {e}")

            await asyncio.sleep(self.weather_interval)

        logger.info("[WEATHER] Scanner stopped")

    async def start(self):
        """Start all scanners."""
        self.running = True

        logger.info("")
        logger.info("[START] Starting all scanners...")
        logger.info("")

        await asyncio.gather(
            self.run_btc_scanner(),
            self.run_weather_scanner()
        )

    def stop(self):
        """Stop all scanners."""
        logger.info("[STOP] Stopping scanners...")
        self.running = False


def main():
    """Main entry point."""
    service = ScannerService()

    def signal_handler(sig, frame):
        print("\n")
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()
