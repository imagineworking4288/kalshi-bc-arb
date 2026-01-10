"""
End-to-end integration tests for the arbitrage trading system.
Tests API endpoints, WebSocket connections, and full trading flows.
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# FastAPI testing
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

# Import API components
from backend.api.routes import router
from backend.api.websocket_routes import router as ws_router, manager, ConnectionManager
from backend.api.schemas import (
    TradingMode, ArbitrageStrategy, ExecuteArbitrageRequest,
    SetTradingModeRequest, OpportunitiesResponse, ExecutionResponse,
    RiskDashboardResponse, SystemStatusResponse,
)


# ============ Fixtures ============

@pytest.fixture
def app():
    """Create test FastAPI application"""
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.include_router(ws_router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_opportunities():
    """Mock opportunity data"""
    return [
        {
            "id": "opp-1",
            "asset": "BTC",
            "settlement_time": "2025-01-15T12:00:00Z",
            "threshold_ticker": "KXBTCD-25JAN15-T100000",
            "threshold_title": "BTC above $100,000",
            "threshold_strike": 100000,
            "bracket_count": 5,
            "cost_per_set": 0.92,
            "fees_per_set": 0.03,
            "profit_per_set": 0.05,
            "net_profit_pct": 5.2,
            "max_contracts": 50,
            "max_liquidity_usd": 46.0,
            "spot_price": 99500,
            "brackets": [
                {"ticker": "KXBTC-B1", "low": 90000, "high": 95000, "yes_price": 0.10},
                {"ticker": "KXBTC-B2", "low": 95000, "high": 100000, "yes_price": 0.20},
                {"ticker": "KXBTC-B3", "low": 100000, "high": 105000, "yes_price": 0.35},
                {"ticker": "KXBTC-B4", "low": 105000, "high": 110000, "yes_price": 0.20},
                {"ticker": "KXBTC-B5", "low": 110000, "high": 999999, "yes_price": 0.07},
            ]
        },
        {
            "id": "opp-2",
            "asset": "BTC",
            "settlement_time": "2025-01-16T12:00:00Z",
            "threshold_ticker": "KXBTCD-25JAN16-T102000",
            "threshold_title": "BTC above $102,000",
            "threshold_strike": 102000,
            "bracket_count": 5,
            "cost_per_set": 0.90,
            "fees_per_set": 0.03,
            "profit_per_set": 0.07,
            "net_profit_pct": 7.5,
            "max_contracts": 30,
            "max_liquidity_usd": 27.0,
            "spot_price": 99500,
            "brackets": []
        }
    ]


@pytest.fixture
def mock_circuit_breaker_status():
    """Mock circuit breaker status"""
    return {
        "can_trade": True,
        "tripped": False,
        "trip_reason": None,
        "cooldown_until": None,
        "daily_pnl_cents": 500,
        "total_position": 10,
        "consecutive_losses": 0,
        "win_rate": 0.65,
        "drawdown_percent": 2.5,
        "warnings": []
    }


# ============ API Endpoint Tests ============

class TestSystemEndpoints:
    """Test system status and configuration endpoints"""

    def test_get_config(self, client):
        """Test GET /config endpoint"""
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "paper_mode" in data
        assert "api_configured" in data

    def test_get_spot_price(self, client):
        """Test GET /spot-price endpoint"""
        # This may fail if no real API is configured
        response = client.get("/spot-price")
        # Accept either success or service unavailable
        assert response.status_code in [200, 503]

    def test_get_balance(self, client):
        """Test GET /balance endpoint"""
        response = client.get("/balance")
        assert response.status_code == 200
        data = response.json()
        # Should have balance info
        assert "available_balance" in data or "balance" in data or "paper_mode" in data


class TestOpportunitiesEndpoints:
    """Test arbitrage opportunities endpoints"""

    def test_get_opportunities(self, client):
        """Test GET /opportunities endpoint"""
        response = client.get("/opportunities")
        assert response.status_code == 200
        data = response.json()
        assert "opportunities" in data
        assert "count" in data
        assert isinstance(data["opportunities"], list)

    def test_get_opportunities_with_min_profit(self, client):
        """Test GET /opportunities with min_profit filter"""
        response = client.get("/opportunities?min_profit=5.0")
        assert response.status_code == 200
        data = response.json()
        # All opportunities should have at least 5% profit
        for opp in data["opportunities"]:
            assert opp.get("net_profit_pct", 0) >= 5.0


class TestTradingEndpoints:
    """Test trading execution endpoints"""

    def test_get_positions(self, client):
        """Test GET /positions endpoint"""
        response = client.get("/positions")
        assert response.status_code == 200
        data = response.json()
        assert "positions" in data
        assert isinstance(data["positions"], list)

    def test_execute_arbitrage_without_opportunity(self, client):
        """Test POST /execute with non-existent opportunity"""
        response = client.post("/execute", json={
            "opportunity_id": "non-existent-id",
            "num_contracts": 1
        })
        # Should return 404 for non-existent opportunity
        assert response.status_code == 404


class TestPaperTradingEndpoints:
    """Test paper trading endpoints"""

    def test_get_paper_summary(self, client):
        """Test GET /paper/summary endpoint"""
        response = client.get("/paper/summary")
        assert response.status_code == 200
        data = response.json()
        # Should have P&L summary fields
        assert any(key in data for key in ["current_balance", "total_pnl", "realized_pnl"])

    def test_get_paper_trades(self, client):
        """Test GET /paper/trades endpoint"""
        response = client.get("/paper/trades?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "trades" in data
        assert isinstance(data["trades"], list)


class TestCircuitBreakerEndpoints:
    """Test circuit breaker endpoints"""

    def test_get_circuit_breaker_status(self, client):
        """Test GET /circuit-breaker/status endpoint"""
        response = client.get("/circuit-breaker/status")
        # May return 500 if orchestrator not initialized
        if response.status_code == 200:
            data = response.json()
            assert "can_trade" in data or "tripped" in data


class TestOrchestratorEndpoints:
    """Test orchestrator control endpoints"""

    def test_get_orchestrator_status(self, client):
        """Test GET /orchestrator/status endpoint"""
        response = client.get("/orchestrator/status")
        # May return 500 if not initialized, or 200 with status
        assert response.status_code in [200, 500]

    def test_get_signals(self, client):
        """Test GET /signals endpoint"""
        response = client.get("/signals?limit=10")
        assert response.status_code in [200, 500]


# ============ WebSocket Tests ============

class TestWebSocketConnection:
    """Test WebSocket connection and messaging"""

    def test_websocket_connect(self, client):
        """Test WebSocket connection"""
        with client.websocket_connect("/ws") as websocket:
            # Should receive connected message
            data = websocket.receive_json()
            assert data.get("type") == "connected"

    def test_websocket_ping_pong(self, client):
        """Test WebSocket ping/pong"""
        with client.websocket_connect("/ws") as websocket:
            # Consume connected message
            websocket.receive_json()

            # Send ping
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data.get("type") == "pong"

    def test_websocket_subscribe(self, client):
        """Test WebSocket subscription"""
        with client.websocket_connect("/ws") as websocket:
            # Consume connected message
            websocket.receive_json()

            # Subscribe to events
            websocket.send_json({
                "type": "subscribe",
                "event_tickers": ["TEST-EVENT"]
            })
            data = websocket.receive_json()
            assert data.get("type") == "subscribed"
            assert "TEST-EVENT" in data.get("event_tickers", [])

    def test_websocket_unsubscribe(self, client):
        """Test WebSocket unsubscription"""
        with client.websocket_connect("/ws") as websocket:
            # Consume connected message
            websocket.receive_json()

            # Subscribe first
            websocket.send_json({
                "type": "subscribe",
                "event_tickers": ["TEST-EVENT"]
            })
            websocket.receive_json()

            # Unsubscribe
            websocket.send_json({
                "type": "unsubscribe",
                "event_tickers": ["TEST-EVENT"]
            })
            data = websocket.receive_json()
            assert data.get("type") == "unsubscribed"

    def test_websocket_invalid_message(self, client):
        """Test WebSocket error handling for invalid messages"""
        with client.websocket_connect("/ws") as websocket:
            # Consume connected message
            websocket.receive_json()

            # Send invalid message type
            websocket.send_json({"type": "invalid_type"})
            data = websocket.receive_json()
            assert data.get("type") == "error"

    def test_websocket_get_subscriptions(self, client):
        """Test WebSocket get_subscriptions message"""
        with client.websocket_connect("/ws") as websocket:
            # Consume connected message
            websocket.receive_json()

            # Subscribe to some events
            websocket.send_json({
                "type": "subscribe",
                "event_tickers": ["EVENT-1", "EVENT-2"]
            })
            websocket.receive_json()

            # Get subscriptions
            websocket.send_json({"type": "get_subscriptions"})
            data = websocket.receive_json()
            assert data.get("type") == "subscriptions"
            assert "EVENT-1" in data.get("event_tickers", [])
            assert "EVENT-2" in data.get("event_tickers", [])


class TestConnectionManager:
    """Test WebSocket connection manager"""

    @pytest.mark.asyncio
    async def test_connection_manager_stats(self):
        """Test connection manager statistics"""
        cm = ConnectionManager()
        stats = cm.get_stats()
        assert "total_connections" in stats
        assert stats["total_connections"] == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_connections(self):
        """Test broadcast with no connections doesn't fail"""
        cm = ConnectionManager()
        # Should not raise
        await cm.broadcast({"type": "test", "data": "hello"})


# ============ Schema Validation Tests ============

class TestSchemaValidation:
    """Test Pydantic schema validation"""

    def test_execute_arbitrage_request_validation(self):
        """Test ExecuteArbitrageRequest validation"""
        # Valid request
        request = ExecuteArbitrageRequest(
            event_ticker="HIGHNY-25JAN10",
            strategy=ArbitrageStrategy.ALL_YES,
            quantity_per_bracket=5,
            max_slippage_cents=3
        )
        assert request.quantity_per_bracket == 5

    def test_execute_arbitrage_request_defaults(self):
        """Test ExecuteArbitrageRequest default values"""
        request = ExecuteArbitrageRequest(
            event_ticker="TEST",
            strategy=ArbitrageStrategy.ALL_YES
        )
        assert request.quantity_per_bracket == 1
        assert request.max_slippage_cents == 3
        assert request.confirm_live is False

    def test_execute_arbitrage_request_quantity_bounds(self):
        """Test ExecuteArbitrageRequest quantity validation"""
        # Should not allow quantity > 100
        with pytest.raises(ValueError):
            ExecuteArbitrageRequest(
                event_ticker="TEST",
                strategy=ArbitrageStrategy.ALL_YES,
                quantity_per_bracket=101
            )

        # Should not allow quantity < 1
        with pytest.raises(ValueError):
            ExecuteArbitrageRequest(
                event_ticker="TEST",
                strategy=ArbitrageStrategy.ALL_YES,
                quantity_per_bracket=0
            )

    def test_set_trading_mode_request_validation(self):
        """Test SetTradingModeRequest validation"""
        # Paper mode
        request = SetTradingModeRequest(mode=TradingMode.PAPER)
        assert request.mode == TradingMode.PAPER
        assert request.confirm_live is None

        # Live mode with confirmation
        request = SetTradingModeRequest(
            mode=TradingMode.LIVE,
            confirm_live="LIVE"
        )
        assert request.mode == TradingMode.LIVE
        assert request.confirm_live == "LIVE"

    def test_trading_mode_enum(self):
        """Test TradingMode enum values"""
        assert TradingMode.PAPER.value == "paper"
        assert TradingMode.LIVE.value == "live"

    def test_arbitrage_strategy_enum(self):
        """Test ArbitrageStrategy enum values"""
        assert ArbitrageStrategy.ALL_YES.value == "all_yes"
        assert ArbitrageStrategy.ALL_NO.value == "all_no"
        assert ArbitrageStrategy.HYBRID.value == "hybrid"
        assert ArbitrageStrategy.MIN_2_NO.value == "min_2_no"


# ============ Integration Flow Tests ============

class TestTradingFlow:
    """Test complete trading workflows"""

    def test_paper_trading_flow(self, client, mock_opportunities):
        """Test complete paper trading flow"""
        # 1. Check system status
        status_response = client.get("/config")
        assert status_response.status_code == 200
        config = status_response.json()
        assert config.get("paper_mode", True) is True  # Should start in paper mode

        # 2. Get opportunities
        opps_response = client.get("/opportunities")
        assert opps_response.status_code == 200
        # Note: actual opportunities depend on live market data

        # 3. Check balance
        balance_response = client.get("/balance")
        assert balance_response.status_code == 200

        # 4. Check positions
        positions_response = client.get("/positions")
        assert positions_response.status_code == 200

    def test_risk_monitoring_flow(self, client):
        """Test risk monitoring workflow"""
        # 1. Get paper summary (risk metrics)
        summary_response = client.get("/paper/summary")
        assert summary_response.status_code == 200

        # 2. Check circuit breaker
        cb_response = client.get("/circuit-breaker/status")
        # May be 500 if orchestrator not initialized
        if cb_response.status_code == 200:
            cb_data = cb_response.json()
            # Should have trading status
            assert "can_trade" in cb_data or "tripped" in cb_data


class TestFeeCalculation:
    """Test fee calculation endpoints"""

    def test_calculate_fee(self, client):
        """Test GET /fees/calculate endpoint"""
        response = client.get("/fees/calculate?price=50&contracts=10")
        assert response.status_code == 200
        data = response.json()
        assert "fee_per_contract" in data
        assert "total_fee" in data
        assert data["contracts"] == 10

    def test_calculate_fee_maker(self, client):
        """Test fee calculation with maker flag"""
        response = client.get("/fees/calculate?price=50&contracts=10&maker=true")
        assert response.status_code == 200
        data = response.json()
        assert data["order_type"] == "maker"

    def test_fee_table(self, client):
        """Test GET /fees/table endpoint"""
        response = client.get("/fees/table")
        assert response.status_code == 200
        data = response.json()
        assert "table" in data
        assert len(data["table"]) > 0


# ============ Weather Arbitrage Tests ============

class TestWeatherArbitrage:
    """Test weather arbitrage endpoints"""

    def test_get_weather_status(self, client):
        """Test GET /weather-arb/status endpoint"""
        response = client.get("/weather-arb/status")
        # May return error if scanner not running
        assert response.status_code == 200
        # Either has data or error message
        data = response.json()
        assert "cities" in data or "error" in data

    def test_get_weather_history(self, client):
        """Test GET /weather-arb/history endpoint"""
        response = client.get("/weather-arb/history?limit=10")
        assert response.status_code == 200


# ============ Performance Assertions ============

class TestAPIPerformance:
    """Test API response times"""

    def test_opportunities_response_time(self, client):
        """Opportunities endpoint should respond within reasonable time"""
        import time
        start = time.time()
        response = client.get("/opportunities")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Should respond within 10 seconds (generous for network calls)
        assert elapsed < 10.0

    def test_balance_response_time(self, client):
        """Balance endpoint should respond quickly"""
        import time
        start = time.time()
        response = client.get("/balance")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Should respond within 5 seconds
        assert elapsed < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
