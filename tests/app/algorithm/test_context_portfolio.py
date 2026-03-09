"""
Consolidated tests for portfolio, position, and allocation context operations.

Merged from:
- test_get_portfolio.py
- test_get_position.py
- test_get_unallocated.py
- test_get_allocated.py
- test_get_number_of_positions.py
- test_has_position.py
- test_has_trading_symbol_position_available.py
- test_close_position.py
"""
import os
from decimal import Decimal
from typing import Dict, Any
from unittest.mock import patch

import pandas as pd

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    CSVOHLCVDataProvider
from tests.resources import BitvavoTestBase, BinanceTestBase
from tests.resources.strategies_for_testing import StrategyOne


class GetAllocatedStrategy(TradingStrategy):
    """Strategy that creates a BUY order on run (for allocation tests)."""
    id = "strategy_one"
    time_unit = TimeUnit.SECOND
    interval = 2

    def run_strategy(self, context, data=None):
        context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            order_side="BUY",
            price=10,
        )

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass


# ---------------------------------------------------------------------------
# BITVAVO-based portfolio tests
# ---------------------------------------------------------------------------

class TestGetPortfolio(BitvavoTestBase):

    def test_get_portfolio(self):
        portfolio = self.app.context.get_portfolio()
        self.assertEqual(Decimal(1000), portfolio.get_unallocated())


class TestGetPosition(BitvavoTestBase):

    def test_get_position(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(Decimal(1000), trading_symbol_position.get_amount())
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertEqual(Decimal(0), btc_position.get_amount())
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position.get_amount())
        self.assertEqual(Decimal(1), btc_position.get_amount())
        self.assertNotEqual(Decimal(990), trading_symbol_position.get_amount())


class TestGetUnallocated(BitvavoTestBase):

    def test_get_unallocated(self):
        portfolio = self.app.context.get_portfolio()
        self.assertEqual(Decimal(1000), portfolio.get_unallocated())


class TestGetAllocated(BitvavoTestBase):

    def test_get_allocated(self):
        self.app.add_strategy(GetAllocatedStrategy)

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 10, "ask": 10, "last": 10}
        ):
            self.app.run(number_of_iterations=1)
            order_service = self.app.container.order_service()
            self.assertEqual(1, order_service.count())
            order_service.check_pending_orders()
            self.assertNotEqual(0, self.app.context.get_allocated())
            self.assertNotEqual(0, self.app.context.get_allocated("BITVAVO"))
            self.assertNotEqual(0, self.app.context.get_allocated("bitvavo"))


class TestGetNumberOfPositions(BitvavoTestBase):

    def test_get_number_of_positions(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1, self.app.context.get_number_of_positions())
        self.assertEqual(Decimal(1000), trading_symbol_position.get_amount())

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 10, "ask": 10, "last": 10}
        ):
            self.app.context.create_limit_order(
                target_symbol="BTC", amount=1, price=10, order_side="BUY",
            )
            order_service = self.app.container.order_service()
            order_service.check_pending_orders()
            self.assertEqual(2, self.app.context.get_number_of_positions())
            self.app.context.create_limit_order(
                target_symbol="DOT", amount=1, price=10, order_side="BUY",
            )
            order_service.check_pending_orders()
            self.assertEqual(3, self.app.context.get_number_of_positions())
            self.app.context.create_limit_order(
                target_symbol="ADA", amount=1, price=10, order_side="BUY",
            )
            self.assertEqual(3, self.app.context.get_number_of_positions())


class TestClosePosition(BitvavoTestBase):

    def setUp(self) -> None:
        super().setUp()
        self.app.add_data_provider(CSVOHLCVDataProvider(
            data_provider_identifier="BTC/EUR-ticker",
            market="BITVAVO",
            symbol="BTC/EUR",
            storage_path=os.path.join(
                self.resource_directory,
                "test_data",
                "ohlcv",
                "OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-08_2023-12-02-00-00.csv"
            ),
            time_frame="1h",
        ), priority=1)

    def test_close_position(self):
        self.app.add_strategy(StrategyOne)
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 990, "ask": 1000, "last": 995}
        ):
            btc_position = self.app.context.get_position("BTC")
            self.assertIsNotNone(btc_position)
            self.assertEqual(0, btc_position.get_amount())

            order_service = self.app.container.order_service()
            order_service.check_pending_orders()

            btc_position = self.app.context.get_position("BTC")
            self.assertIsNotNone(btc_position.get_amount())
            self.assertEqual(Decimal(1), btc_position.get_amount())
            self.assertNotEqual(
                Decimal(990), trading_symbol_position.get_amount()
            )

            self.app.context.close_position(btc_position)
            self.app.run(number_of_iterations=1)

            btc_position = self.app.context.get_position("BTC")
            self.assertEqual(Decimal(0), btc_position.get_amount())


# ---------------------------------------------------------------------------
# Binance-based position tests (has_position, trading_symbol_available)
# ---------------------------------------------------------------------------

class TestHasPosition(BinanceTestBase):
    external_available_symbols = ["BTC/EUR", "DOT/EUR", "ADA/EUR", "ETH/EUR"]

    def test_has_position(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertTrue(self.app.context.has_position("EUR"))
        self.assertFalse(self.app.context.has_position("BTC"))
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertFalse(self.app.context.has_position("BTC"))
        self.assertEqual(0, btc_position.get_amount())
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position.get_amount())
        self.assertEqual(1, btc_position.get_amount())
        self.assertNotEqual(990, trading_symbol_position.amount)
        self.assertTrue(self.app.context.has_position("BTC"))

    def test_position_exists_with_amount_gt(self):
        self.app.context.get_position("EUR")
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertFalse(
            self.app.context.position_exists("BTC", amount_gt=0)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_gt=0)
        )

    def test_position_exists_with_amount_gte(self):
        self.app.context.get_position("EUR")
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_gte=0)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_gte=0)
        )

    def test_position_exists_with_amount_lt(self):
        self.app.context.get_position("EUR")
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_lt=1)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertFalse(
            self.app.context.position_exists("BTC", amount_lt=1)
        )

    def test_position_exists_with_amount_lte(self):
        self.app.context.get_position("EUR")
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_lte=1)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_lte=1)
        )


class TestHasTradingSymbolPositionAvailable(BinanceTestBase):
    external_available_symbols = ["BTC/EUR", "DOT/EUR", "ADA/EUR", "ETH/EUR"]

    def test_has_trading_symbol_available(self):
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available()
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available(
                percentage_of_portfolio=100
            )
        )
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=250, order_side="BUY",
        )
        self.assertFalse(
            self.app.context.has_trading_symbol_position_available(
                percentage_of_portfolio=100
            )
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available()
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available(
                percentage_of_portfolio=75
            )
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available(
                amount_gt=700
            )
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available(
                amount_gte=750
            )
        )
        self.app.context.create_limit_order(
            target_symbol="DOT", amount=1, price=250, order_side="BUY",
        )
        self.assertFalse(
            self.app.context.has_trading_symbol_position_available(
                percentage_of_portfolio=75
            )
        )
        self.assertFalse(
            self.app.context.has_trading_symbol_position_available(
                amount_gt=700
            )
        )
        self.assertFalse(
            self.app.context.has_trading_symbol_position_available(
                amount_gte=750
            )
        )

