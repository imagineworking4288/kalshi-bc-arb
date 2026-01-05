"""
Base strategy interface for all trading strategies.
All strategies (Weather, BTC, Economic) must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class StrategyType(str, Enum):
    """Types of trading strategies."""
    WEATHER = "weather"
    BTC = "btc"
    ECONOMIC = "economic"


class SignalType(str, Enum):
    """Types of trading signals."""
    DIRECTIONAL = "directional"
    ARBITRAGE = "arbitrage"
    SPREAD = "spread"
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    SELL_YES = "sell_yes"
    SELL_NO = "sell_no"


class SignalStatus(str, Enum):
    """Status of a trading signal."""
    PENDING = "pending"
    EXECUTING = "executing"
    EXECUTED = "executed"
    EXPIRED = "expired"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class SignalLeg:
    """Single leg of a multi-leg arbitrage signal."""
    ticker: str
    side: str  # 'yes' or 'no'
    action: str  # 'buy' or 'sell'
    price_cents: int
    strike: Optional[float] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    description: str = ""


@dataclass
class TradingSignal:
    """
    Unified trading signal that can represent:
    - Single-leg directional trades (edge-based)
    - Multi-leg arbitrage opportunities
    """
    strategy_type: StrategyType
    ticker: str  # Primary ticker (or event ticker for arbitrage)
    signal_type: SignalType
    edge_percent: float
    model_prob: float
    market_price: int  # In cents
    recommended_size: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confidence: float = 1.0
    is_arbitrage: bool = False
    legs: List[SignalLeg] = field(default_factory=list)
    status: SignalStatus = SignalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    execution_price: Optional[int] = None
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        strategy_type: StrategyType,
        ticker: str,
        signal_type: SignalType,
        edge_percent: float,
        model_prob: float,
        market_price: int,
        recommended_size: int = 1,
        confidence: float = 1.0,
        is_arbitrage: bool = False,
        legs: List[SignalLeg] = None,
        expires_in_seconds: int = 300,
        metadata: Dict[str, Any] = None
    ) -> 'TradingSignal':
        """Factory method to create a new signal with auto-generated ID."""
        now = datetime.utcnow()
        expires_at = datetime.utcnow()
        expires_at = datetime.fromtimestamp(now.timestamp() + expires_in_seconds)

        return cls(
            id=str(uuid.uuid4()),
            strategy_type=strategy_type,
            ticker=ticker,
            signal_type=signal_type,
            edge_percent=edge_percent,
            model_prob=model_prob,
            market_price=market_price,
            recommended_size=recommended_size,
            confidence=confidence,
            is_arbitrage=is_arbitrage,
            legs=legs or [],
            created_at=now,
            expires_at=expires_at,
            metadata=metadata or {}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "strategy_type": self.strategy_type.value,
            "ticker": self.ticker,
            "signal_type": self.signal_type.value,
            "edge_percent": self.edge_percent,
            "model_prob": self.model_prob,
            "market_price": self.market_price,
            "recommended_size": self.recommended_size,
            "confidence": self.confidence,
            "is_arbitrage": self.is_arbitrage,
            "legs": [
                {
                    "ticker": leg.ticker,
                    "side": leg.side,
                    "action": leg.action,
                    "price_cents": leg.price_cents,
                    "strike": leg.strike,
                    "lower_bound": leg.lower_bound,
                    "upper_bound": leg.upper_bound,
                    "description": leg.description
                }
                for leg in self.legs
            ],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "execution_price": self.execution_price,
            "notes": self.notes,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingSignal':
        """Create signal from dictionary."""
        legs = [
            SignalLeg(
                ticker=leg["ticker"],
                side=leg["side"],
                action=leg["action"],
                price_cents=leg["price_cents"],
                strike=leg.get("strike"),
                lower_bound=leg.get("lower_bound"),
                upper_bound=leg.get("upper_bound"),
                description=leg.get("description", "")
            )
            for leg in data.get("legs", [])
        ]

        return cls(
            id=data["id"],
            strategy_type=StrategyType(data["strategy_type"]),
            ticker=data["ticker"],
            signal_type=SignalType(data["signal_type"]),
            edge_percent=data["edge_percent"],
            model_prob=data["model_prob"],
            market_price=data["market_price"],
            recommended_size=data["recommended_size"],
            confidence=data.get("confidence", 1.0),
            is_arbitrage=data.get("is_arbitrage", False),
            legs=legs,
            status=SignalStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            executed_at=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None,
            execution_price=data.get("execution_price"),
            notes=data.get("notes", ""),
            metadata=data.get("metadata", {})
        )

    def is_expired(self) -> bool:
        """Check if signal has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Each strategy (Weather, BTC, Economic) must implement:
    - scan(): Find opportunities and return signals
    - validate_signal(): Re-check signal before execution
    - scan_interval_seconds: How often to scan
    """

    def __init__(self, strategy_type: StrategyType, name: str):
        self.strategy_type = strategy_type
        self.name = name
        self.enabled = False
        self.scan_count = 0
        self.signals_generated = 0
        self.last_scan_at: Optional[datetime] = None
        self.last_error: Optional[str] = None

    @abstractmethod
    async def scan(self) -> List[TradingSignal]:
        """
        Scan for trading opportunities.

        Returns:
            List of trading signals found during the scan.
        """
        pass

    @abstractmethod
    async def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Validate a signal before execution.

        Called right before executing to ensure the opportunity
        still exists and prices haven't moved unfavorably.

        Args:
            signal: The signal to validate

        Returns:
            True if signal is still valid, False otherwise
        """
        pass

    @property
    @abstractmethod
    def scan_interval_seconds(self) -> float:
        """
        How often this strategy should scan for opportunities.

        Returns:
            Interval in seconds between scans
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get current strategy status for dashboard."""
        return {
            "name": self.name,
            "type": self.strategy_type.value,
            "enabled": self.enabled,
            "scan_count": self.scan_count,
            "signals_generated": self.signals_generated,
            "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "last_error": self.last_error,
            "scan_interval_seconds": self.scan_interval_seconds
        }

    async def run_scan(self) -> List[TradingSignal]:
        """
        Run a scan with error handling and metrics tracking.

        This wraps the abstract scan() method with error handling
        and updates internal metrics.
        """
        try:
            signals = await self.scan()
            self.scan_count += 1
            self.signals_generated += len(signals)
            self.last_scan_at = datetime.utcnow()
            self.last_error = None
            return signals
        except Exception as e:
            self.last_error = str(e)
            self.last_scan_at = datetime.utcnow()
            raise
