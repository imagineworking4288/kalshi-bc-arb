"""
Pre-trade validation to catch errors before order submission.

Validates:
1. Exchange status (is trading active?)
2. Market status (is market open?)
3. Price validity (within bounds, not stale?)
4. Balance sufficiency
5. Position limits
6. Settlement proximity
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from backend.models.kalshi_models import Market, Orderbook, Position
from backend.models.types import MarketStatus
from backend.services.analysis.fee_calculator import calculate_fee
from backend.services.log_config import get_logger

logger = get_logger("validator")


class ValidationError(str, Enum):
    EXCHANGE_CLOSED = "exchange_closed"
    MARKET_NOT_OPEN = "market_not_open"
    MARKET_PAUSED = "market_paused"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    PRICE_DRIFT = "price_drift"
    STALE_DATA = "stale_data"
    POSITION_LIMIT = "position_limit"
    NEAR_SETTLEMENT = "near_settlement"
    INVALID_PRICE = "invalid_price"
    RATE_LIMIT = "rate_limit"


@dataclass
class ValidationResult:
    """Result of pre-trade validation"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error_codes: List[ValidationError] = field(default_factory=list)

    # Price drift detection
    price_drift_detected: bool = False
    max_drift_cents: int = 0
    original_prices: Dict[str, int] = field(default_factory=dict)
    current_prices: Dict[str, int] = field(default_factory=dict)

    # Liquidity check
    liquidity_sufficient: bool = True
    liquidity_shortfall: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_codes": [e.value for e in self.error_codes],
            "price_drift_detected": self.price_drift_detected,
            "max_drift_cents": self.max_drift_cents,
            "liquidity_sufficient": self.liquidity_sufficient,
            "liquidity_shortfall": self.liquidity_shortfall,
        }


@dataclass
class ValidatorConfig:
    """Configuration for validator"""
    max_price_drift_cents: int = 3  # Max acceptable price change
    max_data_age_seconds: float = 5.0  # Max age of orderbook data
    min_hours_to_settlement: float = 0.5  # Don't trade within 30 min of settlement
    max_position_per_market: int = 100
    max_total_position: int = 500
    require_exchange_active: bool = True


class PreTradeValidator:
    """
    Validates trades before submission.

    Usage:
        validator = PreTradeValidator(config)
        result = await validator.validate_arbitrage(
            legs=[...],
            orderbooks={...},
            expected_prices={...},
            balance_cents=10000
        )

        if not result.valid:
            print(f"Validation failed: {result.errors}")
    """

    def __init__(
        self,
        config: Optional[ValidatorConfig] = None,
        kalshi_client=None
    ):
        self.config = config or ValidatorConfig()
        self.kalshi_client = kalshi_client
        self._exchange_status: Optional[Tuple[bool, str]] = None
        self._last_exchange_check: Optional[datetime] = None

    async def validate_arbitrage(
        self,
        legs: List[dict],  # {'ticker', 'side', 'quantity', 'price_cents'}
        orderbooks: Dict[str, Orderbook],
        markets: Dict[str, Market],
        expected_prices: Dict[str, int],  # Expected price when recommendation was made
        balance_cents: int,
        current_positions: Optional[Dict[str, Position]] = None,
    ) -> ValidationResult:
        """
        Validate an arbitrage trade before execution.

        Args:
            legs: List of trade legs
            orderbooks: Current orderbooks for each market
            markets: Market objects for each market
            expected_prices: Prices when opportunity was detected
            balance_cents: Available balance in cents
            current_positions: Current positions (for limit checks)

        Returns:
            ValidationResult with errors, warnings, and drift info
        """
        result = ValidationResult(valid=True)
        current_positions = current_positions or {}

        # 1. Check exchange status
        if self.config.require_exchange_active:
            exchange_ok, exchange_msg = await self._check_exchange_status()
            if not exchange_ok:
                result.valid = False
                result.errors.append(exchange_msg)
                result.error_codes.append(ValidationError.EXCHANGE_CLOSED)

        total_cost = 0
        total_fees = 0
        total_new_position = 0

        for leg in legs:
            ticker = leg['ticker']
            quantity = leg['quantity']
            price_cents = leg['price_cents']
            side = leg.get('side', 'yes')
            expected_price = expected_prices.get(ticker, price_cents)

            market = markets.get(ticker)
            orderbook = orderbooks.get(ticker)

            # 2. Check market status
            if market:
                if market.status != MarketStatus.OPEN:
                    result.valid = False
                    result.errors.append(f"{ticker}: Market is {market.status.value}")
                    result.error_codes.append(ValidationError.MARKET_NOT_OPEN)

                # Check settlement proximity
                if market.is_near_settlement(self.config.min_hours_to_settlement):
                    result.warnings.append(f"{ticker}: Near settlement")
                    ttc = market.time_to_close()
                    if ttc is not None and ttc < 1800:  # 30 minutes
                        result.valid = False
                        result.errors.append(f"{ticker}: Too close to settlement")
                        result.error_codes.append(ValidationError.NEAR_SETTLEMENT)

            # 3. Check orderbook freshness
            if orderbook:
                if orderbook.is_stale(self.config.max_data_age_seconds):
                    result.valid = False
                    result.errors.append(f"{ticker}: Orderbook data is stale")
                    result.error_codes.append(ValidationError.STALE_DATA)

                # 4. Check price drift
                current_price = self._get_current_price(orderbook, side)
                if current_price:
                    result.current_prices[ticker] = current_price
                    result.original_prices[ticker] = expected_price

                    drift = abs(current_price - expected_price)
                    if drift > result.max_drift_cents:
                        result.max_drift_cents = drift

                    if drift > self.config.max_price_drift_cents:
                        result.price_drift_detected = True
                        result.warnings.append(
                            f"{ticker}: Price drifted {drift}c "
                            f"({expected_price}c -> {current_price}c)"
                        )
                        if drift > self.config.max_price_drift_cents * 2:
                            result.valid = False
                            result.errors.append(f"{ticker}: Excessive price drift")
                            result.error_codes.append(ValidationError.PRICE_DRIFT)

                # 5. Check liquidity
                available = self._get_available_liquidity(orderbook, side, price_cents)
                if available < quantity:
                    result.liquidity_sufficient = False
                    result.liquidity_shortfall[ticker] = quantity - available
                    result.warnings.append(
                        f"{ticker}: Only {available} contracts available (need {quantity})"
                    )
            else:
                result.valid = False
                result.errors.append(f"{ticker}: No orderbook data")
                result.error_codes.append(ValidationError.STALE_DATA)

            # Calculate cost
            fee_result = calculate_fee(quantity, price_cents)
            fee = int(fee_result.fee_cents)
            total_cost += (price_cents * quantity)
            total_fees += fee
            total_new_position += quantity

        # 6. Check balance (cost + fees)
        total_required = total_cost + total_fees
        if total_required > balance_cents:
            result.valid = False
            result.errors.append(
                f"Insufficient balance: need {total_required}c (cost: {total_cost}c + fees: {total_fees}c), have {balance_cents}c"
            )
            result.error_codes.append(ValidationError.INSUFFICIENT_BALANCE)

        # 7. Check position limits
        current_total = sum(
            abs(p.position) for p in current_positions.values()
        )

        if current_total + total_new_position > self.config.max_total_position:
            result.valid = False
            result.errors.append(
                f"Position limit exceeded: {current_total + total_new_position} > {self.config.max_total_position}"
            )
            result.error_codes.append(ValidationError.POSITION_LIMIT)

        # Log validation result
        if result.valid:
            logger.info(f"Validation passed for {len(legs)} legs, cost={total_cost}c")
        else:
            logger.warning(f"Validation failed: {result.errors}")

        return result

    async def validate_single_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        price_cents: int,
        orderbook: Optional[Orderbook],
        market: Optional[Market],
        balance_cents: int,
    ) -> ValidationResult:
        """
        Validate a single order.

        Convenience method for non-arbitrage orders.
        """
        legs = [{
            'ticker': ticker,
            'side': side,
            'quantity': quantity,
            'price_cents': price_cents,
        }]

        orderbooks = {ticker: orderbook} if orderbook else {}
        markets = {ticker: market} if market else {}
        expected_prices = {ticker: price_cents}

        return await self.validate_arbitrage(
            legs=legs,
            orderbooks=orderbooks,
            markets=markets,
            expected_prices=expected_prices,
            balance_cents=balance_cents,
        )

    async def _check_exchange_status(self) -> Tuple[bool, str]:
        """Check if exchange is active"""
        now = datetime.now(timezone.utc)

        # Cache for 60 seconds
        if (self._last_exchange_check and
            self._exchange_status is not None and
            (now - self._last_exchange_check).total_seconds() < 60):
            return self._exchange_status

        # Check via API if client available
        if self.kalshi_client:
            try:
                response = await self.kalshi_client.get_exchange_status()
                is_active = response.get('trading_active', True)
                if not is_active:
                    self._exchange_status = (False, "Exchange trading is paused")
                else:
                    self._exchange_status = (True, "")
            except Exception as e:
                logger.warning(f"Failed to check exchange status: {e}")
                # Assume active if check fails
                self._exchange_status = (True, "")
        else:
            # No client, assume active
            self._exchange_status = (True, "")

        self._last_exchange_check = now
        return self._exchange_status

    def _get_current_price(self, orderbook: Orderbook, side: str) -> Optional[int]:
        """Get current price to buy the given side"""
        if side == 'yes':
            return orderbook.yes_ask()
        else:
            return orderbook.no_ask()

    def _get_available_liquidity(
        self,
        orderbook: Orderbook,
        side: str,
        max_price: int
    ) -> int:
        """Get available contracts at or below max price"""
        if side == 'yes':
            return orderbook.yes_liquidity_at_price(max_price)
        else:
            return orderbook.no_liquidity_at_price(max_price)

    def update_config(self, **kwargs):
        """Update validator configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
