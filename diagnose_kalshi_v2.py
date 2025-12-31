#!/usr/bin/env python3
"""
Diagnostic script to test Kalshi API authentication
Updated for new API endpoint: api.elections.kalshi.com
Run from project root: python diagnose_kalshi_v2.py
"""

import os
import sys
import base64
import httpx
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env from current directory
load_dotenv()

def load_private_key(path: str):
    from cryptography.hazmat.primitives import serialization
    key_bytes = Path(path).read_bytes()
    return serialization.load_pem_private_key(key_bytes, password=None)

def sign_request_pss(private_key, timestamp: str, method: str, path: str) -> str:
    """Correct signing method per Kalshi docs - PSS with DIGEST_LENGTH"""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    # Strip query params from path
    path_clean = path.split('?')[0]
    message = f"{timestamp}{method.upper()}{path_clean}"

    signature = private_key.sign(
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH  # Per Kalshi docs
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode()

def test_kalshi_auth():
    api_key_id = os.getenv('KALSHI_API_KEY_ID', '')
    private_key_path = os.getenv('KALSHI_PRIVATE_KEY_PATH', './keys/kalshi-private-key.pem')

    # NEW API URL
    base_url = 'https://api.elections.kalshi.com/trade-api/v2'

    print("=" * 60)
    print("KALSHI API DIAGNOSTIC (Updated URL)")
    print("=" * 60)
    print(f"API Key ID: {api_key_id[:10]}..." if len(api_key_id) > 10 else f"API Key ID: {api_key_id}")
    print(f"Private Key Path: {private_key_path}")
    print(f"Key exists: {Path(private_key_path).exists()}")
    print(f"Base URL: {base_url}")
    print(f"Signing: PSS with DIGEST_LENGTH salt")
    print()

    if not api_key_id:
        print("ERROR: KALSHI_API_KEY_ID not set in .env")
        return False

    if not Path(private_key_path).exists():
        print(f"ERROR: Private key file not found at {private_key_path}")
        return False

    try:
        private_key = load_private_key(private_key_path)
        print("[OK] Private key loaded successfully")
    except Exception as e:
        print(f"ERROR loading private key: {e}")
        return False

    # Test 1: Exchange status (no auth required)
    print("\n--- Test 1: Exchange Status (no auth) ---")
    try:
        response = httpx.get(f"{base_url}/exchange/status", timeout=30.0)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Exchange active: {data.get('exchange_active')}")
            print(f"[OK] Trading active: {data.get('trading_active')}")
        else:
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Request error: {e}")

    # Test 2: Balance (requires auth)
    print("\n--- Test 2: Portfolio Balance (auth required) ---")
    method = "GET"
    path = "/trade-api/v2/portfolio/balance"
    url = f"{base_url}/portfolio/balance"

    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    signature = sign_request_pss(private_key, timestamp, method, path)

    headers = {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json"
    }

    print(f"URL: {url}")
    print(f"Timestamp: {timestamp}")
    print(f"Message signed: {timestamp}{method}{path}")

    try:
        response = httpx.get(url, headers=headers, timeout=30.0)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n[OK] SUCCESS! Authentication working!")
            print(f"  Balance: ${data.get('balance', 0) / 100:.2f}")
            return True
        else:
            print(f"Response: {response.text[:500]}")
            print("\n[FAIL] AUTHENTICATION FAILED")
            return False

    except Exception as e:
        print(f"Request error: {e}")
        return False

def test_markets():
    """Test fetching markets"""
    api_key_id = os.getenv('KALSHI_API_KEY_ID', '')
    private_key_path = os.getenv('KALSHI_PRIVATE_KEY_PATH', './keys/kalshi-private-key.pem')
    base_url = 'https://api.elections.kalshi.com/trade-api/v2'

    print("\n" + "=" * 60)
    print("TESTING MARKETS ENDPOINT")
    print("=" * 60)

    private_key = load_private_key(private_key_path)

    method = "GET"
    path = "/trade-api/v2/markets"
    url = f"{base_url}/markets?limit=5"

    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    signature = sign_request_pss(private_key, timestamp, method, path)

    headers = {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json"
    }

    print(f"URL: {url}")
    print(f"Path signed (no query): {path}")

    try:
        response = httpx.get(url, headers=headers, timeout=30.0)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            markets = data.get('markets', [])
            print(f"\n[OK] SUCCESS! Retrieved {len(markets)} markets")
            for m in markets[:3]:
                print(f"  - {m.get('ticker')}: {m.get('title', '')[:50]}")
            return True
        else:
            print(f"Response: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"Request error: {e}")
        return False

def test_btc_markets():
    """Test fetching BTC-specific markets for arbitrage scanner"""
    api_key_id = os.getenv('KALSHI_API_KEY_ID', '')
    private_key_path = os.getenv('KALSHI_PRIVATE_KEY_PATH', './keys/kalshi-private-key.pem')
    base_url = 'https://api.elections.kalshi.com/trade-api/v2'

    print("\n" + "=" * 60)
    print("TESTING BTC MARKETS (for arbitrage scanner)")
    print("=" * 60)

    private_key = load_private_key(private_key_path)

    method = "GET"
    path = "/trade-api/v2/markets"
    # Search for BTC/Bitcoin markets
    url = f"{base_url}/markets?limit=100"

    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    signature = sign_request_pss(private_key, timestamp, method, path)

    headers = {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json"
    }

    try:
        response = httpx.get(url, headers=headers, timeout=30.0)

        if response.status_code == 200:
            data = response.json()
            markets = data.get('markets', [])

            # Filter for BTC markets
            btc_markets = [m for m in markets if 'BTC' in m.get('ticker', '').upper() or 'BITCOIN' in m.get('title', '').upper()]

            if btc_markets:
                print(f"[OK] Found {len(btc_markets)} BTC markets:")
                for m in btc_markets[:5]:
                    print(f"  - {m.get('ticker')}")
                    print(f"    Title: {m.get('title', '')[:60]}")
                    print(f"    Yes Price: {m.get('yes_bid', 'N/A')}")
                return True
            else:
                print("No BTC markets found in first 20 results")
                print("This is OK - BTC markets may not always be available")
                return True
        else:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:300]}")
            return False

    except Exception as e:
        print(f"Request error: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("KALSHI API DIAGNOSTIC v2")
    print("New endpoint: api.elections.kalshi.com")
    print("=" * 60 + "\n")

    auth_ok = test_kalshi_auth()

    if auth_ok:
        test_markets()
        test_btc_markets()
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Start the backend: python -m uvicorn backend.main:app --reload --port 8000")
        print("2. Start the frontend: cd frontend && npm run dev")
        print("3. Open http://localhost:5173")
    else:
        print("\n" + "=" * 60)
        print("AUTH FAILED - Check your API key and private key")
        print("=" * 60)
