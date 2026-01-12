import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional
from dataclasses import dataclass, asdict

from ..database.connection import db
from ..config import get_settings
from .core.fee_calculator import calculate_fee
from .arbitrage_detector import ArbitrageOpportunity


@dataclass
class PaperOrderResult:
    ticker: str
    side: str
    contracts: int
    fill_price: float
    fee: float
    status: str = "filled"


@dataclass
class PaperTradeResult:
    trade_id: str
    status: str
    orders: List[PaperOrderResult]
    total_cost: float
    total_fees: float
    expected_payout: float
    expected_profit: float
    expected_profit_pct: float
    message: str
    paper_mode: bool = True


class PaperTradingService:
    """Simulates trades locally using real market prices"""

    async def get_balance(self) -> dict:
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT balance, starting_balance FROM paper_account WHERE id = 1"
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "available_balance": row[0],
                    "starting_balance": row[1],
                    "paper_mode": True
                }
            return {"available_balance": 0, "starting_balance": 0, "paper_mode": True}

    async def reset_account(self, starting_balance: Optional[float] = None) -> dict:
        balance = starting_balance or get_settings().paper_starting_balance

        async with db.connection() as conn:
            await conn.execute(
                "UPDATE paper_account SET balance = ?, starting_balance = ?, updated_at = ? WHERE id = 1",
                (balance, balance, datetime.now(timezone.utc).isoformat())
            )
            await conn.execute("DELETE FROM paper_positions")
            await conn.execute("DELETE FROM paper_trades")
            await conn.commit()

        return {"status": "reset", "balance": balance}

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        num_contracts: int
    ) -> PaperTradeResult:
        """Execute full arbitrage by buying YES on all brackets"""
        trade_id = str(uuid.uuid4())

        # Check balance
        balance_info = await self.get_balance()
        available = balance_info["available_balance"]

        total_cost_estimate = opportunity.cost_per_set * num_contracts
        total_fees_estimate = opportunity.fees_per_set * num_contracts
        required = total_cost_estimate + total_fees_estimate

        if required > available:
            return PaperTradeResult(
                trade_id=trade_id,
                status="failed",
                orders=[],
                total_cost=0,
                total_fees=0,
                expected_payout=0,
                expected_profit=0,
                expected_profit_pct=0,
                message=f"Insufficient balance. Need ${required:.2f}, have ${available:.2f}"
            )

        # Build orders for all brackets
        orders: List[PaperOrderResult] = []
        total_cost = 0
        total_fees = 0

        for bracket in opportunity.brackets:
            cost = num_contracts * bracket.yes_price
            fee = calculate_fee(num_contracts, bracket.yes_price)

            orders.append(PaperOrderResult(
                ticker=bracket.ticker,
                side="yes",
                contracts=num_contracts,
                fill_price=bracket.yes_price,
                fee=fee
            ))

            total_cost += cost
            total_fees += fee

        expected_payout = num_contracts  # $1 per contract set
        expected_profit = expected_payout - total_cost - total_fees
        expected_profit_pct = (expected_profit / (total_cost + total_fees)) * 100 if total_cost > 0 else 0

        # Update database
        async with db.connection() as conn:
            # Deduct from balance
            await conn.execute(
                "UPDATE paper_account SET balance = balance - ?, updated_at = ? WHERE id = 1",
                (total_cost + total_fees, datetime.now(timezone.utc).isoformat())
            )

            # Record trade
            await conn.execute("""
                INSERT INTO paper_trades (
                    id, executed_at, asset, total_cost, total_fees, contracts_per_leg,
                    expected_payout, expected_profit, expected_profit_pct, legs_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                datetime.now(timezone.utc).isoformat(),
                opportunity.asset,
                round(total_cost, 2),
                round(total_fees, 2),
                num_contracts,
                expected_payout,
                round(expected_profit, 2),
                round(expected_profit_pct, 2),
                json.dumps([asdict(o) for o in orders]),
                "open"
            ))

            # Create positions
            for order in orders:
                await conn.execute("""
                    INSERT INTO paper_positions (
                        id, created_at, ticker, side, contracts, avg_price,
                        total_cost, total_fees, settlement_time, trade_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    datetime.now(timezone.utc).isoformat(),
                    order.ticker,
                    order.side,
                    order.contracts,
                    order.fill_price,
                    order.contracts * order.fill_price,
                    order.fee,
                    opportunity.settlement_time.isoformat(),
                    trade_id
                ))

            await conn.commit()

        return PaperTradeResult(
            trade_id=trade_id,
            status="success",
            orders=orders,
            total_cost=round(total_cost, 2),
            total_fees=round(total_fees, 2),
            expected_payout=expected_payout,
            expected_profit=round(expected_profit, 2),
            expected_profit_pct=round(expected_profit_pct, 2),
            message=f"Paper arbitrage executed: {len(orders)} bracket positions"
        )

    async def get_positions(self, include_settled: bool = False) -> List[dict]:
        async with db.connection() as conn:
            query = "SELECT * FROM paper_positions"
            if not include_settled:
                query += " WHERE settled = 0"
            query += " ORDER BY created_at DESC"

            cursor = await conn.execute(query)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_trades(self, limit: int = 50) -> List[dict]:
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM paper_trades ORDER BY executed_at DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_pnl_summary(self) -> dict:
        async with db.connection() as conn:
            # Account
            cursor = await conn.execute(
                "SELECT balance, starting_balance FROM paper_account WHERE id = 1"
            )
            account = await cursor.fetchone()

            # Realized P&L
            cursor = await conn.execute(
                "SELECT COALESCE(SUM(realized_pnl), 0) FROM paper_positions WHERE settled = 1"
            )
            realized = (await cursor.fetchone())[0]

            # Open positions value
            cursor = await conn.execute(
                "SELECT COALESCE(SUM(total_cost + total_fees), 0) FROM paper_positions WHERE settled = 0"
            )
            open_value = (await cursor.fetchone())[0]

            # Trade count
            cursor = await conn.execute("SELECT COUNT(*) FROM paper_trades")
            trade_count = (await cursor.fetchone())[0]

            balance = account[0] if account else 0
            starting = account[1] if account else 0

            return {
                "current_balance": round(balance, 2),
                "starting_balance": round(starting, 2),
                "total_pnl": round(balance - starting, 2),
                "total_pnl_pct": round((balance - starting) / starting * 100, 2) if starting else 0,
                "realized_pnl": round(realized, 2),
                "open_positions_value": round(open_value, 2),
                "total_trades": trade_count
            }

    async def settle_position(self, position_id: str, won: bool) -> dict:
        """Manually settle a position (for testing)"""
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM paper_positions WHERE id = ?", (position_id,)
            )
            position = await cursor.fetchone()

            if not position:
                return {"error": "Position not found"}

            payout = position["contracts"] if won else 0
            cost_basis = position["total_cost"] + position["total_fees"]
            realized_pnl = payout - cost_basis

            await conn.execute("""
                UPDATE paper_positions
                SET settled = 1, settled_at = ?, settlement_value = ?, realized_pnl = ?
                WHERE id = ?
            """, (
                datetime.now(timezone.utc).isoformat(),
                1.0 if won else 0.0,
                realized_pnl,
                position_id
            ))

            await conn.execute(
                "UPDATE paper_account SET balance = balance + ? WHERE id = 1",
                (payout,)
            )

            await conn.commit()

            return {
                "position_id": position_id,
                "won": won,
                "payout": payout,
                "realized_pnl": round(realized_pnl, 2)
            }
