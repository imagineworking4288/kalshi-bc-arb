#!/usr/bin/env python3
"""
Diagnostic script to test Kalshi API authentication
Run from project root: python diagnose_kalshi.py
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

def sign_request_pkcs1v15(private_key, timestamp: str, method: str, path: str) -> str:
    """Original signing method (PKCS1v15) - likely WRONG"""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    
    message = f"{timestamp}{method.upper()}{path}"
    signature = private_key.sign(
        message.encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode()

def sign_request_pss(private_key, timestamp: str, method: str, path: str) -> str:
    """Correct signing method (PSS) per Kalshi docs"""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    
    # Strip query params from path
    path_clean = path.split('?')[0]
    message = f"{timestamp}{method.upper()}{path_clean}"
    
    signature = private_key.sign(
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode()

def test_kalshi_auth(use_pss: bool = True):
    api_key_id = os.getenv('KALSHI_API_KEY_ID', '')
    private_key_path = os.getenv('KALSHI_PRIVATE_KEY_PATH', './keys/kalshi-private-key.pem')
    base_url = os.getenv('KALSHI_API_URL', 'https://trading-api.kalshi.com/trade-api/v2')
    
    print("=" * 60)
    print("KALSHI API DIAGNOSTIC")
    print("=" * 60)
    print(f"API Key ID: {api_key_id[:10]}..." if len(api_key_id) > 10 else f"API Key ID: {api_key_id}")
    print(f"Private Key Path: {private_key_path}")
    print(f"Key exists: {Path(private_key_path).exists()}")
    print(f"Base URL: {base_url}")
    print(f"Signing method: {'PSS (correct)' if use_pss else 'PKCS1v15 (legacy)'}")
    print()
    
    if not api_key_id:
        print("ERROR: KALSHI_API_KEY_ID not set in .env")
        return
    
    if not Path(private_key_path).exists():
        print(f"ERROR: Private key file not found at {private_key_path}")
        return
    
    try:
        private_key = load_private_key(private_key_path)
        print("✓ Private key loaded successfully")
    except Exception as e:
        print(f"ERROR loading private key: {e}")
        return
    
    # Test endpoint - simple balance check
    method = "GET"
    path = "/trade-api/v2/portfolio/balance"
    url = f"{base_url}/portfolio/balance"
    
    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    
    if use_pss:
        signature = sign_request_pss(private_key, timestamp, method, path)
    else:
        signature = sign_request_pkcs1v15(private_key, timestamp, method, path)
    
    headers = {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json"
    }
    
    print(f"\nTesting: {method} {url}")
    print(f"Timestamp: {timestamp}")
    print(f"Message being signed: {timestamp}{method}{path.split('?')[0]}")
    print()
    
    try:
        response = httpx.get(url, headers=headers, timeout=30.0)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            print("\n✓ SUCCESS! Authentication working correctly.")
        elif response.status_code == 401:
            print("\n✗ AUTHENTICATION FAILED (401)")
            print("Possible causes:")
            print("  1. Wrong API Key ID")
            print("  2. Wrong private key file")
            print("  3. Wrong signing method (try both PSS and PKCS1v15)")
            print("  4. Clock skew (timestamp too old)")
        else:
            print(f"\n? Unexpected status code: {response.status_code}")
            
    except Exception as e:
        print(f"Request error: {e}")

def test_markets_endpoint(use_pss: bool = True):
    """Test the markets endpoint specifically"""
    api_key_id = os.getenv('KALSHI_API_KEY_ID', '')
    private_key_path = os.getenv('KALSHI_PRIVATE_KEY_PATH', './keys/kalshi-private-key.pem')
    base_url = os.getenv('KALSHI_API_URL', 'https://trading-api.kalshi.com/trade-api/v2')
    
    print("\n" + "=" * 60)
    print("TESTING MARKETS ENDPOINT")
    print("=" * 60)
    
    private_key = load_private_key(private_key_path)
    
    method = "GET"
    path = "/trade-api/v2/markets"
    url = f"{base_url}/markets?status=active&limit=10"
    
    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    
    if use_pss:
        signature = sign_request_pss(private_key, timestamp, method, path)
    else:
        signature = sign_request_pkcs1v15(private_key, timestamp, method, path)
    
    headers = {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json"
    }
    
    print(f"Testing: {method} {url}")
    print(f"Path signed (no query): {path}")
    
    try:
        response = httpx.get(url, headers=headers, timeout=30.0)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            markets = data.get('markets', [])
            print(f"✓ SUCCESS! Retrieved {len(markets)} markets")
            if markets:
                print(f"  First market: {markets[0].get('ticker', 'N/A')}")
        else:
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"Request error: {e}")

if __name__ == "__main__":
    print("\n### TEST 1: PSS Signing (Correct per Kalshi docs) ###")
    test_kalshi_auth(use_pss=True)
    
    print("\n\n### TEST 2: PKCS1v15 Signing (Legacy/Wrong) ###")
    test_kalshi_auth(use_pss=False)
    
    print("\n\n### TEST 3: Markets Endpoint with PSS ###")
    test_markets_endpoint(use_pss=True)
