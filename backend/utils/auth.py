"""Kalshi API authentication utilities"""

import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey


class KalshiAuth:
    """Handles RSA-based authentication for Kalshi API"""

    def __init__(self, api_key_id: str, private_key_path: str):
        self.api_key_id = api_key_id
        self.private_key: Optional[RSAPrivateKey] = None
        self._private_key_path = private_key_path
        self._load_private_key()

    def _load_private_key(self) -> None:
        """Load private key from PEM file"""
        key_path = Path(self._private_key_path)
        if not key_path.exists():
            # Allow running without key for demo purposes
            return

        key_data = key_path.read_bytes()
        self.private_key = serialization.load_pem_private_key(
            key_data, password=None
        )

    def get_auth_headers(self, method: str, path: str) -> dict:
        """
        Generate authentication headers for a request.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path (e.g., /markets)

        Returns:
            Dictionary of headers to include in the request
        """
        if not self.private_key or not self.api_key_id:
            return {}

        # Generate timestamp in milliseconds
        timestamp = str(int(datetime.utcnow().timestamp() * 1000))

        # Build message to sign: timestamp + method + path
        message = f"{timestamp}{method}{path}"

        # Sign with RSA PKCS1v15 and SHA256
        signature = self.private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    def get_ws_auth_message(self) -> Optional[dict]:
        """
        Generate WebSocket authentication message.

        Returns:
            Dictionary to send as authentication message, or None if not configured
        """
        if not self.private_key or not self.api_key_id:
            return None

        timestamp = str(int(datetime.utcnow().timestamp() * 1000))
        message = f"{timestamp}GET/trade-api/ws/v2"

        signature = self.private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        return {
            "type": "auth",
            "params": {
                "api_key": self.api_key_id,
                "signature": base64.b64encode(signature).decode(),
                "timestamp": timestamp,
            }
        }

    @property
    def is_configured(self) -> bool:
        """Check if authentication is properly configured"""
        return bool(self.private_key and self.api_key_id)
