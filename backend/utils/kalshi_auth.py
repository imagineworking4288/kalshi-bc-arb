import base64
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class KalshiAuth:
    """RSA-based authentication for Kalshi API using PSS signatures"""

    def __init__(self, api_key_id: str, private_key_path: str):
        self.api_key_id = api_key_id
        self.private_key = self._load_key(private_key_path)

    def _load_key(self, path: str):
        key_bytes = Path(path).read_bytes()
        return serialization.load_pem_private_key(key_bytes, password=None)

    def get_headers(self, method: str, path: str) -> dict:
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))

        # Strip query parameters from path before signing
        path_without_query = path.split('?')[0]
        message = f"{timestamp}{method.upper()}{path_without_query}"

        # Use PSS padding (not PKCS1v15) as required by Kalshi
        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "Content-Type": "application/json"
        }
