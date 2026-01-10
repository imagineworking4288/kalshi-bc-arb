"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


# ============ Enums ============

class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class ArbitrageStrategy(str, Enum):
    ALL_YES = "all_yes"
    ALL_NO = "all_no"
    HYBRID = "hybrid"
    MIN_2_NO = "min_2_no"


class OrderSide(str, Enum):
    YES = "yes"
    NO = "no"


class OrderAction(str, Enum):
    BUY = "buy"
    SELL = "sell"


# ============ Request Schemas ============

class ExecuteArbitrageRequest(BaseModel):
    """Request to execute an arbitrage opportunity"""
    event_ticker: str
    strategy: ArbitrageStrategy
    quantity_per_bracket: int = Field(default=1, ge=1, le=100)
    max_slippage_cents: int = Field(default=3, ge=0, le=10)
    confirm_live: bool = Field(default=False, description="Must be True for live trading")

    class Config:
        json_schema_extra = {
            "example": {
                "event_ticker": "HIGHNY-25JAN10",
                "strategy": "all_yes",
                "quantity_per_bracket": 1,
                "max_slippage_cents": 3,
                "confirm_live": False
            }
        }


class SetTradingModeRequest(BaseModel):
    """Request to change trading mode"""
    mode: TradingMode
    confirm_live: Optional[str] = Field(
        default=None,
        description="Must be 'LIVE' to enable live trading"
    )


class SubscribeMarketsRequest(BaseModel):
    """Request to subscribe to market updates"""
    event_tickers: List[str]


class ExecuteOpportunityRequest(BaseModel):
    """Request to execute a specific opportunity"""
    opportunity_id: str
    num_contracts: int = Field(default=1, ge=1, le=100)
    confirm_live: bool = Field(default=False)


# ============ Response Schemas ============

class MarketResponse(BaseModel):
    """Single market data"""
    ticker: str
    event_ticker: str
    title: str
    status: str
    yes_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    no_bid: Optional[int] = None
    no_ask: Optional[int] = None
    floor_strike: Optional[float] = None
    cap_strike: Optional[float] = None
    volume_24h: int = 0
    close_time: Optional[str] = None
    is_stale: bool = False


class OrderbookLevelResponse(BaseModel):
    """Single orderbook level"""
    price_cents: int
    quantity: int


class OrderbookResponse(BaseModel):
    """Orderbook data"""
    ticker: str
    yes_bids: List[OrderbookLevelResponse] = []
    no_bids: List[OrderbookLevelResponse] = []
    yes_ask: Optional[int] = None
    no_ask: Optional[int] = None
    timestamp: str
    is_stale: bool = False


class ArbitrageLegResponse(BaseModel):
    """Single leg of arbitrage opportunity"""
    ticker: str
    side: str
    action: str = "buy"
    quantity: int = 1
    price_cents: int
    fee_cents: float
    bracket_label: str = ""


class ArbitrageOpportunityResponse(BaseModel):
    """Arbitrage opportunity details"""
    event_ticker: str
    event_title: str
    strategy: str
    legs: List[ArbitrageLegResponse]
    total_cost_cents: int
    total_fees_cents: float
    expected_profit_cents: float
    profit_after_fees_cents: float
    roi_percent: float
    confidence: float = 1.0
    warnings: List[str] = []
    is_stale: bool = False
    calculated_at: str
    expires_at: Optional[str] = None


class OpportunitiesResponse(BaseModel):
    """List of current opportunities"""
    opportunities: List[ArbitrageOpportunityResponse]
    last_updated: str
    trading_mode: str


class ExecutionLegResult(BaseModel):
    """Result for single execution leg"""
    ticker: str
    status: str
    requested_quantity: int
    filled_quantity: int
    requested_price: int
    fill_price: Optional[int] = None
    fee_cents: float
    error: Optional[str] = None


class ExecutionResponse(BaseModel):
    """Execution result"""
    execution_id: str
    status: str  # completed, partial, failed, rolled_back
    success: bool
    fully_filled: bool
    legs: List[ExecutionLegResult] = []
    total_cost_cents: int
    total_fees_cents: float
    profit_cents: Optional[float] = None
    errors: List[str] = []
    warnings: List[str] = []
    execution_time_ms: int = 0
    trading_mode: str


class PositionResponse(BaseModel):
    """Current position"""
    ticker: str
    side: str
    quantity: int
    avg_cost_cents: float
    unrealized_pnl_cents: int = 0
    current_price: Optional[int] = None


class CircuitBreakerResponse(BaseModel):
    """Circuit breaker status"""
    can_trade: bool
    tripped: bool
    trip_reason: Optional[str] = None
    cooldown_until: Optional[str] = None
    daily_pnl_cents: int = 0
    total_position: int = 0
    consecutive_losses: int = 0
    win_rate: float = 0.5
    drawdown_percent: float = 0.0
    warnings: List[str] = []


class RiskDashboardResponse(BaseModel):
    """Complete risk dashboard data"""
    timestamp: str
    trading_mode: str
    balance_cents: int

    # P&L
    daily_pnl_cents: int = 0
    total_pnl_cents: int = 0
    unrealized_pnl_cents: int = 0

    # Positions
    positions: List[PositionResponse] = []
    total_position: int = 0

    # Performance
    trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    win_rate: float = 0.5

    # Risk
    drawdown_percent: float = 0.0
    circuit_breaker: CircuitBreakerResponse


class SystemStatusResponse(BaseModel):
    """System health status"""
    status: str  # healthy, degraded, error
    websocket_connected: bool
    exchange_active: bool
    trading_mode: str
    last_data_update: Optional[str] = None
    active_subscriptions: int = 0
    warnings: List[str] = []


# ============ WebSocket Messages ============

class WSMessage(BaseModel):
    """Base WebSocket message"""
    type: str
    data: Any
    timestamp: str


class WSOrderbookUpdate(BaseModel):
    """WebSocket orderbook update"""
    type: str = "orderbook_update"
    ticker: str
    orderbook: OrderbookResponse


class WSOpportunityUpdate(BaseModel):
    """WebSocket opportunity update"""
    type: str = "opportunity_update"
    opportunities: List[ArbitrageOpportunityResponse]


class WSRiskUpdate(BaseModel):
    """WebSocket risk metrics update"""
    type: str = "risk_update"
    risk: RiskDashboardResponse


class WSExecutionUpdate(BaseModel):
    """WebSocket execution result update"""
    type: str = "execution_update"
    execution: ExecutionResponse


class WSSubscriptionConfirm(BaseModel):
    """WebSocket subscription confirmation"""
    type: str = "subscribed"
    event_tickers: List[str]
    timestamp: str


class WSError(BaseModel):
    """WebSocket error message"""
    type: str = "error"
    message: str
    code: Optional[str] = None
