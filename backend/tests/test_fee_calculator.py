"""Tests for fee calculator"""

import pytest
from services.fee_calculator import (
    calculate_fee,
    calculate_order_cost,
    calculate_arbitrage_cost,
    calculate_max_contracts_for_budget,
    OrderLeg,
)


class TestCalculateFee:
    def test_fee_at_50_cents(self):
        """Test fee calculation at 50 cent price"""
        fee = calculate_fee(100, 0.50)
        # 0.07 * 100 * 0.5 * 0.5 = 1.75, ceil to 1.75
        assert fee == 1.75

    def test_fee_at_10_cents(self):
        """Test fee at low price"""
        fee = calculate_fee(100, 0.10)
        # 0.07 * 100 * 0.1 * 0.9 = 0.63, ceil to 0.63
        assert fee == 0.63

    def test_fee_at_90_cents(self):
        """Test fee at high price"""
        fee = calculate_fee(100, 0.90)
        # 0.07 * 100 * 0.9 * 0.1 = 0.63, ceil to 0.63
        assert fee == 0.63

    def test_fee_at_extremes(self):
        """Test fee at extreme prices"""
        assert calculate_fee(100, 0.01) > 0
        assert calculate_fee(100, 0.99) > 0
        assert calculate_fee(100, 0.0) == 0
        assert calculate_fee(100, 1.0) == 0

    def test_fee_with_different_contract_counts(self):
        """Test fee scales with contract count"""
        fee_100 = calculate_fee(100, 0.50)
        fee_200 = calculate_fee(200, 0.50)
        assert fee_200 == fee_100 * 2


class TestCalculateOrderCost:
    def test_basic_order_cost(self):
        """Test basic order cost calculation"""
        leg = OrderLeg(ticker="TEST", side="yes", contracts=100, price=0.50)
        result = calculate_order_cost(leg)

        assert result.contracts == 100
        assert result.price == 0.50
        assert result.cost == 50.0
        assert result.fee == 1.75
        assert result.total == 51.75


class TestCalculateArbitrageCost:
    def test_multi_leg_arbitrage(self):
        """Test multi-leg arbitrage cost calculation"""
        legs = [
            OrderLeg(ticker="A", side="yes", contracts=100, price=0.30),
            OrderLeg(ticker="B", side="yes", contracts=100, price=0.40),
            OrderLeg(ticker="C", side="yes", contracts=100, price=0.25),
        ]

        result = calculate_arbitrage_cost(legs)

        # Total cost should be sum of all prices * contracts
        assert result["total_cost"] == 95.0  # (0.30 + 0.40 + 0.25) * 100

        # Guaranteed payout for 100 contract sets
        assert result["guaranteed_payout"] == 100

        # Net profit should be positive (arb opportunity)
        assert result["net_profit"] > 0

    def test_empty_legs(self):
        """Test with no legs"""
        result = calculate_arbitrage_cost([])
        assert result["total"] == 0
        assert result["net_profit"] == 0


class TestCalculateMaxContracts:
    def test_max_contracts_calculation(self):
        """Test max contracts for a budget"""
        # Simple case: single price at 50 cents
        max_contracts = calculate_max_contracts_for_budget(100, [0.50])
        # Should be able to buy ~200 contracts (less fees)
        assert max_contracts > 0
        assert max_contracts <= 200

    def test_max_contracts_with_multiple_prices(self):
        """Test max contracts with multiple legs"""
        prices = [0.30, 0.40, 0.25]
        max_contracts = calculate_max_contracts_for_budget(100, prices)
        # Total cost per set is 0.95, so ~105 contracts max
        assert max_contracts > 0
        assert max_contracts <= 105

    def test_zero_budget(self):
        """Test with zero budget"""
        max_contracts = calculate_max_contracts_for_budget(0, [0.50])
        assert max_contracts == 0
