"""
Services module for Kalshi trading platform.

Import services explicitly when needed to avoid circular imports:
    from backend.services.kalshi_client import KalshiClient
    from backend.services.btc_arb_scanner import BTCArbScanner
"""

# Don't auto-import - let modules import what they need explicitly
# This prevents circular import issues with config
