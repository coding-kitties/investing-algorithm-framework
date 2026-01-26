"""
Tests for proportional scaling behavior in TradingStrategy.

When multiple buy signals fire simultaneously and the total requested
allocation exceeds available funds, all orders should be scaled down
proportionally to ensure fair allocation across all symbols.
"""
import os
from datetime import datetime, timezone
from typing import Dict, Any
from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch
import pandas as pd

from investing_algorithm_framework import (
    TradingStrategy, PositionSize, TimeUnit, DataSource, DataType
)
from investing_algorithm_framework.domain import OrderSide, INDEX_DATETIME


class MultiSymbolStrategy(TradingStrategy):
    """Test strategy with multiple symbols for proportional scaling tests."""
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC", "ETH", "SOL", "ADA", "XRP"]

    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
        PositionSize(symbol="ETH", percentage_of_portfolio=20.0),
        PositionSize(symbol="SOL", percentage_of_portfolio=20.0),
        PositionSize(symbol="ADA", percentage_of_portfolio=20.0),
        PositionSize(symbol="XRP", percentage_of_portfolio=20.0),
    ]

    data_sources = [
        DataSource(
            identifier="BTC_data",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            window_size=100
        ),
        DataSource(
            identifier="ETH_data",
            data_type=DataType.OHLCV,
            symbol="ETH/EUR",
            time_frame="2h",
            market="BITVAVO",
            window_size=100
        ),
        DataSource(
            identifier="SOL_data",
            data_type=DataType.OHLCV,
            symbol="SOL/EUR",
            time_frame="2h",
            market="BITVAVO",
            window_size=100
        ),
        DataSource(
            identifier="ADA_data",
            data_type=DataType.OHLCV,
            symbol="ADA/EUR",
            time_frame="2h",
            market="BITVAVO",
            window_size=100
        ),
        DataSource(
            identifier="XRP_data",
            data_type=DataType.OHLCV,
            symbol="XRP/EUR",
            time_frame="2h",
            market="BITVAVO",
            window_size=100
        ),
    ]

    def __init__(self, buy_signals_config=None):
        """
        Args:
            buy_signals_config: Dict mapping symbol to bool indicating
                if buy signal should fire
        """
        super().__init__()
        self.buy_signals_config = buy_signals_config or {
            "BTC": True, "ETH": True, "SOL": True, "ADA": True, "XRP": True
        }
        self.created_orders = []

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        signals = {}
        for symbol in self.symbols:
            # Create a series with the configured buy signal
            should_buy = self.buy_signals_config.get(symbol, False)
            signals[symbol] = pd.Series([should_buy])
        return signals

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        signals = {}
        for symbol in self.symbols:
            signals[symbol] = pd.Series([False])
        return signals

    def create_limit_order(self, **kwargs):
        """Override to track created orders."""
        self.created_orders.append(kwargs)
        # Return a mock order with an id
        mock_order = Mock()
        mock_order.id = len(self.created_orders)
        return mock_order


class TestProportionalScaling(TestCase):
    """Tests for proportional scaling of buy orders."""

    def _create_mock_context(self, unallocated=1000.0, allocated=0.0):
        """Create a mock context for testing."""
        context = Mock()

        # Mock portfolio
        portfolio = Mock()
        portfolio.get_unallocated.return_value = unallocated
        portfolio.allocated = allocated

        context.get_portfolio.return_value = portfolio
        context.get_unallocated.return_value = unallocated
        context.get_trading_symbol.return_value = "EUR"

        # Mock prices (all same for simplicity)
        context.get_latest_price.return_value = 100.0

        # Mock has_open_orders and has_position
        context.has_open_orders.return_value = False
        context.has_position.return_value = False

        # Mock trade retrieval
        mock_trade = Mock()
        context.get_trade.return_value = mock_trade

        # Mock add_stop_loss and add_take_profit
        context.add_stop_loss = Mock()
        context.add_take_profit = Mock()

        # Config with INDEX_DATETIME
        context.config = {INDEX_DATETIME: datetime.now(timezone.utc)}

        return context

    def test_no_scaling_when_funds_sufficient(self):
        """
        Test that orders are not scaled when total allocation
        is within available funds.
        """
        strategy = MultiSymbolStrategy(buy_signals_config={
            "BTC": True, "ETH": True, "SOL": False, "ADA": False, "XRP": False
        })

        # 1000 EUR available, only 2 symbols want 20% each = 400 EUR total
        context = self._create_mock_context(unallocated=1000.0, allocated=0.0)
        strategy.context = context

        # Run the strategy
        strategy.run_strategy(context, data={})

        # Should have 2 orders (BTC and ETH)
        self.assertEqual(len(strategy.created_orders), 2)

        # Each order should be for 200 EUR (20% of 1000)
        for order in strategy.created_orders:
            # amount is in asset units, price is 100, so 200 EUR = 2 units
            expected_amount = 200.0 / 100.0  # 2.0 units
            self.assertAlmostEqual(order['amount'], expected_amount, places=2)

    def test_proportional_scaling_when_funds_insufficient(self):
        """
        Test that all orders are scaled proportionally when total
        allocation exceeds available funds.
        """
        strategy = MultiSymbolStrategy(buy_signals_config={
            "BTC": True, "ETH": True, "SOL": True, "ADA": True, "XRP": True
        })

        # Only 800 EUR available, but 5 symbols want 20% each = 1000 EUR total
        # Scale factor should be 800/1000 = 0.8
        context = self._create_mock_context(unallocated=800.0, allocated=200.0)
        strategy.context = context

        # Run the strategy
        strategy.run_strategy(context, data={})

        # Should have 5 orders
        self.assertEqual(len(strategy.created_orders), 5)

        # Each order should be scaled to 160 EUR (200 * 0.8)
        for order in strategy.created_orders:
            # 160 EUR at price 100 = 1.6 units
            expected_amount = 160.0 / 100.0  # 1.6 units
            self.assertAlmostEqual(order['amount'], expected_amount, places=2)

    def test_fair_allocation_regardless_of_symbol_order(self):
        """
        Test that allocation is fair regardless of the order of symbols.
        All symbols should get the same scaled amount.
        """
        # Test with different symbol orders
        for symbols_order in [
            ["BTC", "ETH", "SOL", "ADA", "XRP"],
            ["XRP", "ADA", "SOL", "ETH", "BTC"],
            ["SOL", "BTC", "XRP", "ETH", "ADA"],
        ]:
            strategy = MultiSymbolStrategy()
            strategy.symbols = symbols_order
            strategy.created_orders = []  # Reset orders for each iteration

            # 500 EUR available, 5 symbols want 200 each = 1000 total
            # Scale factor = 0.5
            context = self._create_mock_context(unallocated=500.0, allocated=500.0)
            strategy.context = context

            strategy.run_strategy(context, data={})

            # All orders should be scaled equally
            amounts = [order['amount'] for order in strategy.created_orders]

            # Should have 5 orders
            self.assertEqual(len(strategy.created_orders), 5,
                f"Expected 5 orders for symbol order {symbols_order}")

            # All amounts should be equal (100 EUR / 100 price = 1.0 units)
            for amount in amounts:
                self.assertAlmostEqual(amount, 1.0, places=2)

    def test_skip_orders_when_scaled_amount_too_small(self):
        """
        Test that orders are skipped when the scaled amount is too small.
        """
        strategy = MultiSymbolStrategy(buy_signals_config={
            "BTC": True, "ETH": True, "SOL": True, "ADA": True, "XRP": True
        })

        # Only 0.04 EUR available, 5 symbols want 200 each
        # Each would get 0.008 EUR which is below 0.01 threshold
        context = self._create_mock_context(unallocated=0.04, allocated=999.96)
        strategy.context = context

        strategy.run_strategy(context, data={})

        # All orders should be skipped
        self.assertEqual(len(strategy.created_orders), 0)

    def test_partial_buy_signals(self):
        """
        Test scaling when only some symbols have buy signals.
        """
        strategy = MultiSymbolStrategy(buy_signals_config={
            "BTC": True, "ETH": True, "SOL": True, "ADA": False, "XRP": False
        })

        # 450 EUR available, 3 symbols want 200 each = 600 total
        # Scale factor = 450/600 = 0.75
        context = self._create_mock_context(unallocated=450.0, allocated=550.0)
        strategy.context = context

        strategy.run_strategy(context, data={})

        # Should have 3 orders
        self.assertEqual(len(strategy.created_orders), 3)

        # Each order should be scaled to 150 EUR (200 * 0.75)
        for order in strategy.created_orders:
            expected_amount = 150.0 / 100.0  # 1.5 units
            self.assertAlmostEqual(order['amount'], expected_amount, places=2)

    def test_existing_positions_excluded_from_buy(self):
        """
        Test that symbols with existing positions don't get buy orders.
        """
        strategy = MultiSymbolStrategy(buy_signals_config={
            "BTC": True, "ETH": True, "SOL": True, "ADA": True, "XRP": True
        })

        context = self._create_mock_context(unallocated=1000.0, allocated=0.0)

        # BTC and ETH already have positions
        def has_position_side_effect(symbol, **kwargs):
            return symbol in ["BTC", "ETH"]

        context.has_position = Mock(side_effect=has_position_side_effect)
        strategy.context = context

        strategy.run_strategy(context, data={})

        # Should only have 3 orders (SOL, ADA, XRP)
        self.assertEqual(len(strategy.created_orders), 3)

        # Verify the symbols that got orders
        ordered_symbols = [order['target_symbol'] for order in strategy.created_orders]
        self.assertNotIn("BTC", ordered_symbols)
        self.assertNotIn("ETH", ordered_symbols)
        self.assertIn("SOL", ordered_symbols)
        self.assertIn("ADA", ordered_symbols)
        self.assertIn("XRP", ordered_symbols)

    def test_open_orders_excluded_from_buy(self):
        """
        Test that symbols with open orders don't get new buy orders.
        """
        strategy = MultiSymbolStrategy(buy_signals_config={
            "BTC": True, "ETH": True, "SOL": True, "ADA": True, "XRP": True
        })

        context = self._create_mock_context(unallocated=1000.0, allocated=0.0)

        # SOL has an open order
        def has_open_orders_side_effect(target_symbol=None, **kwargs):
            return target_symbol == "SOL"

        context.has_open_orders = Mock(side_effect=has_open_orders_side_effect)
        strategy.context = context

        strategy.run_strategy(context, data={})

        # Should only have 4 orders (BTC, ETH, ADA, XRP - not SOL)
        self.assertEqual(len(strategy.created_orders), 4)

        ordered_symbols = [order['target_symbol'] for order in strategy.created_orders]
        self.assertNotIn("SOL", ordered_symbols)


class TestProportionalScalingEdgeCases(TestCase):
    """Edge case tests for proportional scaling."""

    def _create_mock_context(self, unallocated=1000.0, allocated=0.0):
        """Create a mock context for testing."""
        context = Mock()

        portfolio = Mock()
        portfolio.get_unallocated.return_value = unallocated
        portfolio.allocated = allocated

        context.get_portfolio.return_value = portfolio
        context.get_unallocated.return_value = unallocated
        context.get_trading_symbol.return_value = "EUR"
        context.get_latest_price.return_value = 100.0
        context.has_open_orders.return_value = False
        context.has_position.return_value = False

        mock_trade = Mock()
        context.get_trade.return_value = mock_trade
        context.add_stop_loss = Mock()
        context.add_take_profit = Mock()
        context.config = {INDEX_DATETIME: datetime.now(timezone.utc)}

        return context

    def test_zero_available_funds(self):
        """Test behavior when no funds are available."""
        strategy = MultiSymbolStrategy()
        context = self._create_mock_context(unallocated=0.0, allocated=1000.0)
        strategy.context = context

        strategy.run_strategy(context, data={})

        # No orders should be created
        self.assertEqual(len(strategy.created_orders), 0)

    def test_exact_match_no_scaling(self):
        """Test when total allocation exactly matches available funds."""
        strategy = MultiSymbolStrategy(buy_signals_config={
            "BTC": True, "ETH": True, "SOL": True, "ADA": True, "XRP": True
        })

        # Exactly 1000 EUR available, 5 symbols want 200 each = 1000 total
        context = self._create_mock_context(unallocated=1000.0, allocated=0.0)
        strategy.context = context

        strategy.run_strategy(context, data={})

        # Should have 5 orders, no scaling needed
        self.assertEqual(len(strategy.created_orders), 5)

        for order in strategy.created_orders:
            expected_amount = 200.0 / 100.0  # 2.0 units (no scaling)
            self.assertAlmostEqual(order['amount'], expected_amount, places=2)

    def test_single_symbol_no_scaling(self):
        """Test with a single symbol (no scaling logic triggered)."""
        strategy = MultiSymbolStrategy(buy_signals_config={
            "BTC": True, "ETH": False, "SOL": False, "ADA": False, "XRP": False
        })

        context = self._create_mock_context(unallocated=1000.0, allocated=0.0)
        strategy.context = context

        strategy.run_strategy(context, data={})

        # Should have 1 order
        self.assertEqual(len(strategy.created_orders), 1)
        self.assertEqual(strategy.created_orders[0]['target_symbol'], "BTC")

    def test_very_small_scale_factor(self):
        """Test with a very small scale factor."""
        strategy = MultiSymbolStrategy()

        # 10 EUR available, 5 symbols want 200 each = 1000 total
        # Scale factor = 0.01
        context = self._create_mock_context(unallocated=10.0, allocated=990.0)
        strategy.context = context

        strategy.run_strategy(context, data={})

        # Each would get 2 EUR, which is above 0.01 threshold
        self.assertEqual(len(strategy.created_orders), 5)

        for order in strategy.created_orders:
            expected_amount = 2.0 / 100.0  # 0.02 units
            self.assertAlmostEqual(order['amount'], expected_amount, places=4)


class TestProportionalScalingWithFixedAmount(TestCase):
    """Tests for proportional scaling with fixed amount position sizes."""

    def _create_mock_context(self, unallocated=1000.0, allocated=0.0):
        context = Mock()

        portfolio = Mock()
        portfolio.get_unallocated.return_value = unallocated
        portfolio.allocated = allocated

        context.get_portfolio.return_value = portfolio
        context.get_unallocated.return_value = unallocated
        context.get_trading_symbol.return_value = "EUR"
        context.get_latest_price.return_value = 100.0
        context.has_open_orders.return_value = False
        context.has_position.return_value = False

        mock_trade = Mock()
        context.get_trade.return_value = mock_trade
        context.add_stop_loss = Mock()
        context.add_take_profit = Mock()
        context.config = {INDEX_DATETIME: datetime.now(timezone.utc)}

        return context

    def test_fixed_amount_scaling(self):
        """Test proportional scaling with fixed amount position sizes."""

        class FixedAmountStrategy(MultiSymbolStrategy):
            position_sizes = [
                PositionSize(symbol="BTC", fixed_amount=300.0),
                PositionSize(symbol="ETH", fixed_amount=200.0),
                PositionSize(symbol="SOL", fixed_amount=100.0),
            ]
            symbols = ["BTC", "ETH", "SOL"]

        strategy = FixedAmountStrategy(buy_signals_config={
            "BTC": True, "ETH": True, "SOL": True
        })

        # 300 EUR available, total wanted = 600 EUR
        # Scale factor = 0.5
        context = self._create_mock_context(unallocated=300.0, allocated=700.0)
        strategy.context = context

        strategy.run_strategy(context, data={})

        self.assertEqual(len(strategy.created_orders), 3)

        # Find orders by symbol
        orders_by_symbol = {
            order['target_symbol']: order for order in strategy.created_orders
        }

        # BTC: 300 * 0.5 = 150 EUR -> 1.5 units at price 100
        self.assertAlmostEqual(orders_by_symbol['BTC']['amount'], 1.5, places=2)
        # ETH: 200 * 0.5 = 100 EUR -> 1.0 units
        self.assertAlmostEqual(orders_by_symbol['ETH']['amount'], 1.0, places=2)
        # SOL: 100 * 0.5 = 50 EUR -> 0.5 units
        self.assertAlmostEqual(orders_by_symbol['SOL']['amount'], 0.5, places=2)


if __name__ == '__main__':
    import unittest
    unittest.main()

