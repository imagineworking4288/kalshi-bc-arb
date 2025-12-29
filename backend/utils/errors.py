"""Custom exception classes"""


class KalshiError(Exception):
    """Base exception for Kalshi-related errors"""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class AuthenticationError(KalshiError):
    """Raised when authentication fails"""
    pass


class RateLimitError(KalshiError):
    """Raised when rate limit is exceeded"""
    pass


class OrderError(KalshiError):
    """Raised when order placement fails"""
    pass


class InsufficientBalanceError(KalshiError):
    """Raised when account has insufficient balance"""
    pass


class MarketClosedError(KalshiError):
    """Raised when attempting to trade on a closed market"""
    pass


class ArbitrageError(Exception):
    """Base exception for arbitrage-related errors"""
    pass


class OpportunityExpiredError(ArbitrageError):
    """Raised when an opportunity is no longer available"""
    pass


class LiquidityError(ArbitrageError):
    """Raised when there's insufficient liquidity"""
    pass
