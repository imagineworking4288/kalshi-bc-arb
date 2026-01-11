"""
Data models for the ExecutionGateway.

Provides structured request/response models for trade execution
with built-in validation and computed properties.
"""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator, computed_field


class ExecutionLeg(BaseModel):
    """Single leg of a multi-leg execution request."""
    ticker: str
    side: Literal['yes', 'no']
    action: Literal['buy', 'sell']
    contracts: int = Field(gt=0, description="Number of contracts (must be positive)")
    price_cents: int = Field(ge=1, le=99, description="Price in cents (1-99)")
    price_type: Literal['limit', 'market'] = 'limit'


class ExecutionRequest(BaseModel):
    """Request to execute one or more trade legs."""
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    source: Literal['orchestrator', 'manual', 'auto_trader', 'btc_arb', 'strategy']
    signal_id: Optional[str] = None
    mode: Literal['paper', 'live', 'dual']
    legs: List[ExecutionLeg]
    atomic: bool = True
    max_slippage_cents: int = Field(default=2, ge=0)
    timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator('legs')
    @classmethod
    def validate_legs_not_empty(cls, v):
        if not v:
            raise ValueError('At least one execution leg is required')
        return v

    @classmethod
    def single_order(
        cls,
        ticker: str,
        side: Literal['yes', 'no'],
        action: Literal['buy', 'sell'],
        contracts: int,
        price_cents: int,
        mode: Literal['paper', 'live', 'dual'],
        source: Literal['orchestrator', 'manual', 'auto_trader', 'btc_arb', 'strategy'] = 'manual',
        signal_id: Optional[str] = None,
    ) -> 'ExecutionRequest':
        """Factory for single-leg orders."""
        return cls(
            source=source,
            signal_id=signal_id,
            mode=mode,
            legs=[ExecutionLeg(
                ticker=ticker,
                side=side,
                action=action,
                contracts=contracts,
                price_cents=price_cents,
            )],
            atomic=True,
        )

    @classmethod
    def arbitrage(
        cls,
        legs: List[ExecutionLeg],
        mode: Literal['paper', 'live', 'dual'],
        source: Literal['orchestrator', 'manual', 'auto_trader', 'btc_arb', 'strategy'] = 'orchestrator',
        signal_id: Optional[str] = None,
        max_slippage_cents: int = 2,
    ) -> 'ExecutionRequest':
        """Factory for multi-leg arbitrage orders."""
        return cls(
            source=source,
            signal_id=signal_id,
            mode=mode,
            legs=legs,
            atomic=True,
            max_slippage_cents=max_slippage_cents,
        )


class LegResult(BaseModel):
    """Result of executing a single leg."""
    ticker: str
    side: Literal['yes', 'no']
    action: Literal['buy', 'sell']
    requested_contracts: int
    filled_contracts: int
    requested_price_cents: int
    fill_price_cents: Optional[int] = None
    fee_cents: int = 0
    status: Literal['filled', 'partial', 'failed', 'cancelled']
    order_id: Optional[str] = None
    error: Optional[str] = None
    slippage_cents: int = 0


class ExecutionResult(BaseModel):
    """Complete result of an execution request from the ExecutionGateway."""
    request_id: str
    success: bool
    mode: Literal['paper', 'live', 'dual']
    legs: List[LegResult]
    total_cost_cents: int
    total_fees_cents: int
    execution_time_ms: int
    audit_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None

    @computed_field
    @property
    def total_filled_contracts(self) -> int:
        return sum(leg.filled_contracts for leg in self.legs)

    @computed_field
    @property
    def average_fill_price(self) -> Optional[float]:
        filled_legs = [leg for leg in self.legs if leg.fill_price_cents is not None]
        if not filled_legs:
            return None
        total_value = sum(leg.fill_price_cents * leg.filled_contracts for leg in filled_legs)
        total_contracts = sum(leg.filled_contracts for leg in filled_legs)
        return total_value / total_contracts if total_contracts > 0 else None

    @computed_field
    @property
    def had_slippage(self) -> bool:
        return any(leg.slippage_cents != 0 for leg in self.legs)
