"""
Integration test that verifies the entire application starts correctly
and all major endpoints respond.

Run with: python test_integration_startup.py
"""
import subprocess
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import requests
except ImportError:
    print("Installing requests for integration test...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

BASE_URL = "http://localhost:8099"
STARTUP_TIMEOUT = 20
TEST_TIMEOUT = 5


def wait_for_startup(proc, timeout=STARTUP_TIMEOUT):
    """Wait for server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is not None:
            # Process died
            stdout, stderr = proc.communicate()
            print("[FAIL] Server crashed during startup!")
            print("STDOUT:", stdout.decode()[-2000:] if stdout else "")
            print("STDERR:", stderr.decode()[-2000:] if stderr else "")
            return False

        try:
            r = requests.get(f"{BASE_URL}/health", timeout=1)
            if r.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass

        time.sleep(0.5)

    print("[FAIL] Server did not start within timeout")
    return False


def test_endpoint(name, method, path, expected_status=200, json_body=None):
    """Test a single endpoint."""
    try:
        url = f"{BASE_URL}{path}"
        if method == "GET":
            r = requests.get(url, timeout=TEST_TIMEOUT)
        elif method == "POST":
            r = requests.post(url, json=json_body or {}, timeout=TEST_TIMEOUT)
        else:
            print(f"[WARN] Unknown method: {method}")
            return False

        if r.status_code == expected_status:
            print(f"[PASS] {name}: {method} {path} -> {r.status_code}")
            return True
        else:
            print(f"[FAIL] {name}: {method} {path} -> {r.status_code} (expected {expected_status})")
            print(f"   Response: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"[FAIL] {name}: {method} {path} -> Error: {e}")
        return False


def main():
    print("=" * 60)
    print("KALSHI BOT INTEGRATION TEST")
    print("=" * 60)

    # Start the server
    print("\n[INFO] Starting server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8099", "--log-level", "warning"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    try:
        if not wait_for_startup(proc):
            return 1

        print("[PASS] Server started successfully!\n")

        # Test endpoints
        print("[INFO] Testing endpoints...\n")

        results = []

        # Core endpoints
        results.append(test_endpoint("Health", "GET", "/health"))
        results.append(test_endpoint("Config", "GET", "/api/config"))
        results.append(test_endpoint("Balance", "GET", "/api/balance"))
        results.append(test_endpoint("Positions", "GET", "/api/positions"))

        # BTC Arbitrage
        results.append(test_endpoint("BTC Arb Status", "GET", "/api/btc-arb/status"))

        # Auto Trader
        results.append(test_endpoint("Auto Trader Status", "GET", "/api/auto-trader/status"))

        # Orchestrator
        results.append(test_endpoint("Orchestrator Status", "GET", "/api/orchestrator/status"))

        # Circuit Breaker
        results.append(test_endpoint("Circuit Breaker", "GET", "/api/circuit-breaker/status"))

        # Weather (may return empty data, that's OK)
        results.append(test_endpoint("Weather Status", "GET", "/api/weather-arb/status"))

        # Emergency endpoints
        results.append(test_endpoint("Emergency Status", "GET", "/api/emergency/status"))

        # Summary
        print("\n" + "=" * 60)
        passed = sum(results)
        total = len(results)
        print(f"RESULTS: {passed}/{total} tests passed")

        if passed == total:
            print("[PASS] ALL TESTS PASSED")
            return 0
        else:
            print("[FAIL] SOME TESTS FAILED")
            return 1

    finally:
        # Clean up
        print("\n[INFO] Stopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Done.")


if __name__ == "__main__":
    sys.exit(main())
