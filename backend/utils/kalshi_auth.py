import base64
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class KalshiAuth:
    """RSA-based authentication for Kalshi API"""

    def __init__(self, api_key_id: str, private_key_path: str):
        self.api_key_id = api_key_id
        self.private_key = self._load_key(private_key_path)

    def _load_key(self, path: str):
        key_bytes = Path(path).read_bytes()
        return serialization.load_pem_private_key(key_bytes, password=None)

    def get_headers(self, method: str, path: str) -> dict:
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        message = f"{timestamp}{method.upper()}{path}"

        signature = self.private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "Content-Type": "application/json"
        }
