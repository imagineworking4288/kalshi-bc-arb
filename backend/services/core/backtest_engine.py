"""
Backtesting engine for historical strategy simulation.
Runs strategies against historical data to evaluate performance.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from .base_strategy import BaseStrategy, TradingSignal, StrategyType, SignalStatus
from .kelly_sizing import KellySizing, KellyConfig

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""
    start_date: datetime
    end_date: datetime
    initial_balance_cents: int = 100000  # $1000 default
    kelly_fraction: float = 0.25
    min_edge_percent: float = 5.0
    max_position_per_trade: int = 100
    slippage_cents: int = 1  # Assumed slippage per trade
    include_fees: bool = True


@dataclass
class BacktestTrade:
    """Record of a simulated trade."""
    signal_id: str
    ticker: str
    strategy_type: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: int
    exit_price: Optional[int]
    contracts: int
    side: str  # "yes" or "no"
    is_arbitrage: bool
    pnl_cents: int = 0
    fees_cents: int = 0
    status: str = "open"  # "open", "won", "lost", "expired"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal_id": self.signal_id,
            "ticker": self.ticker,
            "strategy_type": self.strategy_type,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "contracts": self.contracts,
            "side": self.side,
            "is_arbitrage": self.is_arbitrage,
            "pnl_cents": self.pnl_cents,
            "fees_cents": self.fees_cents,
            "status": self.status
        }


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    config: BacktestConfig
    final_balance_cents: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl_cents: int
    total_fees_cents: int
    max_drawdown_percent: float
    sharpe_ratio: float
    profit_factor: float
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)
    strategy_breakdown: Dict[str, Dict] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config": {
                "start_date": self.config.start_date.isoformat(),
                "end_date": self.config.end_date.isoformat(),
                "initial_balance_cents": self.config.initial_balance_cents,
                "kelly_fraction": self.config.kelly_fraction,
                "min_edge_percent": self.config.min_edge_percent
            },
            "final_balance_cents": self.final_balance_cents,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "total_pnl_cents": self.total_pnl_cents,
            "total_fees_cents": self.total_fees_cents,
            "max_drawdown_percent": round(self.max_drawdown_percent, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "profit_factor": round(self.profit_factor, 3),
            "equity_curve": self.equity_curve,
            "trades": [t.to_dict() for t in self.trades],
            "strategy_breakdown": self.strategy_breakdown,
            "errors": self.errors
        }


class BacktestEngine:
    """
    Historical backtesting engine.

    Simulates strategy performance against historical market data.
    Uses the same Kelly sizing and position limits as live trading.
    """

    def __init__(self, db):
        """
        Initialize backtest engine.

        Args:
            db: Database connection for historical data
        """
        self.db = db

    async def run(
        self,
        strategy: BaseStrategy,
        config: BacktestConfig
    ) -> BacktestResult:
        """
        Run a backtest for a single strategy.

        Args:
            strategy: Strategy to test
            config: Backtest configuration

        Returns:
            BacktestResult with performance metrics
        """
        # Initialize Kelly sizing with backtest config
        kelly = KellySizing(KellyConfig(
            fraction=config.kelly_fraction,
            min_edge_percent=config.min_edge_percent,
            max_contracts=config.max_position_per_trade
        ))

        # State tracking
        balance = config.initial_balance_cents
        peak_balance = balance
        max_drawdown = 0.0
        trades: List[BacktestTrade] = []
        equity_curve: List[Dict] = []
        daily_returns: List[float] = []
        errors: List[str] = []

        # Get historical signals/opportunities
        historical_data = await self._get_historical_data(
            strategy.strategy_type,
            config.start_date,
            config.end_date
        )

        if not historical_data:
            return BacktestResult(
                config=config,
                final_balance_cents=balance,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl_cents=0,
                total_fees_cents=0,
                max_drawdown_percent=0.0,
                sharpe_ratio=0.0,
                profit_factor=0.0,
                equity_curve=[],
                trades=[],
                strategy_breakdown={},
                errors=["No historical data found for date range"]
            )

        # Track daily PnL for Sharpe calculation
        current_date = None
        daily_pnl = 0

        # Process each historical data point
        for data_point in historical_data:
            try:
                # Track daily boundaries for equity curve
                point_date = data_point.get("timestamp", datetime.utcnow()).date()
                if current_date is None:
                    current_date = point_date

                if point_date != current_date:
                    # New day - record equity and daily return
                    equity_curve.append({
                        "date": current_date.isoformat(),
                        "balance_cents": balance,
                        "daily_pnl_cents": daily_pnl
                    })
                    if balance > 0:
                        daily_returns.append(daily_pnl / balance)
                    daily_pnl = 0
                    current_date = point_date

                # Create signal from historical data
                signal = self._data_to_signal(data_point, strategy.strategy_type)
                if not signal:
                    continue

                # Apply Kelly sizing
                if signal.is_arbitrage:
                    # For arbitrage, use recommended size or calculate
                    contracts = min(
                        signal.recommended_size,
                        config.max_position_per_trade
                    )
                else:
                    kelly_result = kelly.calculate(
                        signal.model_prob,
                        signal.market_price,
                        balance
                    )
                    if kelly_result.contracts == 0:
                        continue
                    contracts = kelly_result.contracts

                # Calculate trade cost
                entry_price = signal.market_price + config.slippage_cents
                trade_cost = contracts * entry_price

                # Skip if insufficient balance
                if trade_cost > balance:
                    continue

                # Calculate fee
                fee = 0
                if config.include_fees:
                    fee = self._calculate_fee(contracts, entry_price)

                # Simulate trade outcome
                outcome = await self._get_outcome(data_point)
                exit_price = outcome.get("exit_price", 0)
                won = outcome.get("won", False)

                # Calculate PnL
                if signal.is_arbitrage:
                    # Arbitrage: guaranteed profit if executed
                    pnl = (100 - entry_price) * contracts - fee
                elif won:
                    # Won: payout is 100 cents per contract
                    pnl = (100 - entry_price) * contracts - fee
                else:
                    # Lost: lose entire stake
                    pnl = -entry_price * contracts - fee

                # Create trade record
                trade = BacktestTrade(
                    signal_id=signal.id,
                    ticker=signal.ticker,
                    strategy_type=strategy.strategy_type.value,
                    entry_time=signal.created_at,
                    exit_time=outcome.get("exit_time"),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    contracts=contracts,
                    side="yes",
                    is_arbitrage=signal.is_arbitrage,
                    pnl_cents=pnl,
                    fees_cents=fee,
                    status="won" if won else "lost"
                )
                trades.append(trade)

                # Update balance
                balance += pnl
                daily_pnl += pnl

                # Track drawdown
                if balance > peak_balance:
                    peak_balance = balance
                drawdown = (peak_balance - balance) / peak_balance * 100 if peak_balance > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)

            except Exception as e:
                errors.append(f"Error processing data point: {str(e)}")
                continue

        # Final day equity
        if current_date:
            equity_curve.append({
                "date": current_date.isoformat(),
                "balance_cents": balance,
                "daily_pnl_cents": daily_pnl
            })
            if balance > 0:
                daily_returns.append(daily_pnl / balance)

        # Calculate metrics
        winning_trades = sum(1 for t in trades if t.pnl_cents > 0)
        losing_trades = sum(1 for t in trades if t.pnl_cents < 0)
        total_trades = len(trades)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        total_pnl = sum(t.pnl_cents for t in trades)
        total_fees = sum(t.fees_cents for t in trades)

        # Profit factor
        gross_profit = sum(t.pnl_cents for t in trades if t.pnl_cents > 0)
        gross_loss = abs(sum(t.pnl_cents for t in trades if t.pnl_cents < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

        # Sharpe ratio (annualized)
        sharpe = self._calculate_sharpe(daily_returns)

        # Strategy breakdown
        breakdown = self._calculate_breakdown(trades)

        return BacktestResult(
            config=config,
            final_balance_cents=balance,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl_cents=total_pnl,
            total_fees_cents=total_fees,
            max_drawdown_percent=max_drawdown,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            equity_curve=equity_curve,
            trades=trades,
            strategy_breakdown=breakdown,
            errors=errors
        )

    async def run_multiple(
        self,
        strategies: List[BaseStrategy],
        config: BacktestConfig
    ) -> Dict[str, BacktestResult]:
        """
        Run backtests for multiple strategies.

        Args:
            strategies: List of strategies to test
            config: Backtest configuration

        Returns:
            Dict mapping strategy type to result
        """
        results = {}
        for strategy in strategies:
            result = await self.run(strategy, config)
            results[strategy.strategy_type.value] = result
        return results

    async def _get_historical_data(
        self,
        strategy_type: StrategyType,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Get historical market data for backtesting.

        This queries the historical_opportunities or market_snapshots table.
        """
        async with self.db.connection() as conn:
            # Try historical opportunities first
            cursor = await conn.execute("""
                SELECT * FROM historical_opportunities
                WHERE strategy_type = ?
                AND timestamp >= ?
                AND timestamp <= ?
                ORDER BY timestamp ASC
            """, (strategy_type.value, start_date.isoformat(), end_date.isoformat()))

            rows = await cursor.fetchall()
            if rows:
                return [dict(row) for row in rows]

            # Fallback to signals_v2 history
            cursor = await conn.execute("""
                SELECT * FROM signals_v2
                WHERE strategy_type = ?
                AND created_at >= ?
                AND created_at <= ?
                ORDER BY created_at ASC
            """, (strategy_type.value, start_date.isoformat(), end_date.isoformat()))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def _get_outcome(self, data_point: Dict) -> Dict:
        """
        Get the outcome of a historical trade.

        Looks up actual market resolution or simulates based on model probability.
        """
        # Check if outcome is stored
        if "outcome" in data_point:
            return data_point["outcome"]

        if "won" in data_point:
            return {
                "won": data_point["won"],
                "exit_price": 100 if data_point["won"] else 0,
                "exit_time": data_point.get("resolution_time")
            }

        # Simulate based on model probability
        # For backtesting, assume model was correct at its confidence level
        import random
        model_prob = data_point.get("model_prob", 0.5)
        won = random.random() < model_prob

        return {
            "won": won,
            "exit_price": 100 if won else 0,
            "exit_time": None
        }

    def _data_to_signal(
        self,
        data: Dict,
        strategy_type: StrategyType
    ) -> Optional[TradingSignal]:
        """Convert historical data to a TradingSignal."""
        try:
            from .base_strategy import SignalType
            import uuid

            return TradingSignal(
                id=data.get("id", str(uuid.uuid4())),
                strategy_type=strategy_type,
                ticker=data.get("ticker", ""),
                signal_type=SignalType(data.get("signal_type", "directional")),
                edge_percent=data.get("edge_percent", 0),
                model_prob=data.get("model_prob", 0.5),
                market_price=data.get("market_price", 50),
                recommended_size=data.get("recommended_size", 10),
                confidence=data.get("confidence", 1.0),
                is_arbitrage=bool(data.get("is_arbitrage", 0)),
                legs=[],
                status=SignalStatus.PENDING,
                created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow()
            )
        except Exception as e:
            logger.warning(f"Failed to convert data to signal: {e}")
            return None

    def _calculate_fee(self, contracts: int, price_cents: int) -> int:
        """Calculate Kalshi trading fee."""
        import math
        if contracts <= 0 or price_cents <= 0 or price_cents >= 100:
            return 0
        price = price_cents / 100.0
        fee = 0.07 * contracts * price * (1 - price)
        return int(math.ceil(fee * 100))

    def _calculate_sharpe(self, daily_returns: List[float]) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(daily_returns) < 2:
            return 0.0

        import statistics
        mean_return = statistics.mean(daily_returns)
        std_return = statistics.stdev(daily_returns)

        if std_return == 0:
            return 0.0

        # Annualize (252 trading days)
        annualized_return = mean_return * 252
        annualized_std = std_return * (252 ** 0.5)

        return annualized_return / annualized_std

    def _calculate_breakdown(self, trades: List[BacktestTrade]) -> Dict[str, Dict]:
        """Calculate performance breakdown by strategy."""
        breakdown = {}

        for trade in trades:
            st = trade.strategy_type
            if st not in breakdown:
                breakdown[st] = {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "total_pnl_cents": 0,
                    "total_fees_cents": 0
                }

            breakdown[st]["total_trades"] += 1
            if trade.pnl_cents > 0:
                breakdown[st]["winning_trades"] += 1
            breakdown[st]["total_pnl_cents"] += trade.pnl_cents
            breakdown[st]["total_fees_cents"] += trade.fees_cents

        # Calculate win rates
        for st in breakdown:
            total = breakdown[st]["total_trades"]
            wins = breakdown[st]["winning_trades"]
            breakdown[st]["win_rate"] = wins / total if total > 0 else 0

        return breakdown
