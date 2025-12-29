"""FastAPI dependencies"""

from functools import lru_cache

from ..config import Settings, get_settings
from ..services.kalshi_client import KalshiClient
from ..services.cf_benchmarks_client import CFBenchmarksClient
from ..services.market_service import MarketService
from ..services.arbitrage_engine import ArbitrageEngine
from ..services.opportunity_logger import OpportunityLogger
from ..services.analytics_service import AnalyticsService
from ..services.trade_executor import TradeExecutor
from ..services.position_tracker import PositionTracker


@lru_cache
def get_kalshi_client() -> KalshiClient:
    """Get Kalshi client instance"""
    return KalshiClient()


@lru_cache
def get_cf_benchmarks_client() -> CFBenchmarksClient:
    """Get CF Benchmarks client instance"""
    return CFBenchmarksClient()


def get_market_service() -> MarketService:
    """Get market service instance"""
    return MarketService(get_kalshi_client())


def get_arbitrage_engine() -> ArbitrageEngine:
    """Get arbitrage engine instance"""
    return ArbitrageEngine()


def get_opportunity_logger() -> OpportunityLogger:
    """Get opportunity logger instance"""
    return OpportunityLogger()


def get_analytics_service() -> AnalyticsService:
    """Get analytics service instance"""
    return AnalyticsService()


def get_trade_executor() -> TradeExecutor:
    """Get trade executor instance"""
    return TradeExecutor(get_kalshi_client())


def get_position_tracker() -> PositionTracker:
    """Get position tracker instance"""
    return PositionTracker()
