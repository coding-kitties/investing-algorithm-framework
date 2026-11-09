import unittest
from unittest.mock import MagicMock

from investing_algorithm_framework.app.context import Context
from investing_algorithm_framework.domain import (
    OperationalException, OrderSide, OrderType, TradeStatus,
)


class TestOrderPrecision(unittest.TestCase):
    def setUp(self):
        self.context = Context(*(MagicMock() for _ in range(10)))
        self.context.configuration_service.config = {}
        portfolio = self.context.portfolio_service.find.return_value
        portfolio.id = "portfolio"
        portfolio.trading_symbol = "EUR"
        portfolio.get_net_size.return_value = 1000
        portfolio.get_trading_symbol.return_value = "EUR"
        self.context.portfolio_service.get.return_value = portfolio
        self.context.get_latest_price = MagicMock(return_value=10)
        self.context._blotter = MagicMock()
        self.context._blotter.place_order.side_effect = lambda data, _: data
        self.position = self.context.position_service.find.return_value
        self.position.symbol = "BTC"
        self.position.get_symbol.return_value = "BTC"
        self.position.get_amount.return_value = 1.23456789
        self.trade = self.context.trade_service.get.return_value
        self.trade.status = TradeStatus.OPEN.value
        self.trade.available_amount = 1.23456789

    def _create(self, method, **kwargs):
        defaults = {
            "create_order": dict(
                price=10, order_type=OrderType.STOP_LIMIT,
                order_side=OrderSide.BUY, amount=1.23456789, stop_price=11,
            ),
            "create_limit_order": dict(
                price=10, order_side=OrderSide.BUY, amount=1.23456789,
            ),
            "create_market_order": dict(
                order_side=OrderSide.BUY, amount=1.23456789,
            ),
            "create_short_order": dict(price=10, amount=1.23456789),
            "create_cover_order": dict(price=10, amount=1.23456789),
            "create_limit_buy_order": dict(price=10, amount=1.23456789),
            "create_limit_sell_order": dict(price=10, amount=1.23456789),
            "create_market_buy_order": dict(amount=1.23456789),
            "create_market_sell_order": dict(amount=1.23456789),
        }
        return getattr(self.context, method)(
            target_symbol="BTC", **(defaults[method] | kwargs)
        )

    def test_explicit_and_default_precision_across_order_apis(self):
        for method in (
            "create_order", "create_limit_order", "create_market_order",
            "create_short_order", "create_cover_order",
            "create_limit_buy_order", "create_limit_sell_order",
            "create_market_buy_order", "create_market_sell_order",
        ):
            for precision, expected in ((None, 1.23456789), (6, 1.234567)):
                with self.subTest(method=method, precision=precision):
                    order = self._create(method, precision=precision)
                    self.assertEqual(order["amount"], expected)

    def test_trading_symbol_sizing_is_rounded_after_conversion(self):
        for method in ("create_limit_order", "create_market_order"):
            for amount in (None, 9.0):
                with self.subTest(method=method, amount=amount):
                    order = self._create(
                        method, amount=amount,
                        amount_trading_symbol=12.3456789, precision=6,
                    )
                    self.assertEqual(order["amount"], 1.234567)

    def test_percentage_sizing(self):
        self.position.get_amount.return_value = -1.23456789
        cases = (
            ("create_limit_order", {"percentage_of_portfolio": 1.23456789}),
            ("create_market_order", {"percentage_of_portfolio": 1.23456789}),
            ("create_short_order", {"percentage_of_portfolio": 1.23456789}),
            ("create_cover_order", {"percentage_of_position": 100}),
        )
        for method, sizing in cases:
            with self.subTest(method=method):
                order = self._create(
                    method, amount=None, precision=6, **sizing
                )
                self.assertEqual(order["amount"], 1.234567)

    def test_sell_percentage_sizing(self):
        for method in (
            "create_limit_order", "create_market_order",
            "create_limit_sell_order", "create_market_sell_order",
        ):
            with self.subTest(method=method):
                sizing = dict(
                    amount=None, percentage_of_position=100, precision=6,
                )
                if method in ("create_limit_order", "create_market_order"):
                    sizing["order_side"] = OrderSide.SELL
                order = self._create(method, **sizing)
                self.assertEqual(order["amount"], 1.234567)

    def test_zero_rounded_amount_is_rejected_before_submission(self):
        for method in (
            "create_order", "create_limit_order", "create_market_order",
            "create_short_order", "create_cover_order",
            "create_limit_buy_order", "create_limit_sell_order",
            "create_market_buy_order", "create_market_sell_order",
        ):
            with self.subTest(method=method):
                with self.assertRaisesRegex(
                    OperationalException, "zero after rounding"
                ):
                    self._create(method, amount=1e-7, precision=6)
        self.context._blotter.place_order.assert_not_called()

    def test_invalid_precision_and_nonfinite_amount_are_rejected(self):
        for precision in (-1, 1.5, True, "6"):
            with self.subTest(precision=precision):
                with self.assertRaisesRegex(
                    OperationalException, "non-negative integer"
                ):
                    self._create("create_limit_order", precision=precision)
        for amount in (float("nan"), float("inf"), -1):
            with self.subTest(amount=amount):
                with self.assertRaisesRegex(
                    OperationalException, "finite and non-negative"
                ):
                    self._create(
                        "create_limit_order", amount=amount, precision=6
                    )
        self.context._blotter.place_order.assert_not_called()

    def test_value_and_percentage_helpers(self):
        for method, sizing in (
            ("order_value", {"value": 12.3456789}),
            ("order_percent", {"percent": 1.23456789}),
        ):
            with self.subTest(method=method):
                order = getattr(self.context, method)(
                    target_symbol="BTC", order_side=OrderSide.BUY,
                    price=10, precision=6, **sizing,
                )
                self.assertEqual(order["amount"], 1.234567)

    def test_target_rounding_preserves_no_op_and_order_side(self):
        for current, target, expected_side in (
            (0, 1.23456789, "BUY"), (2.46913578, 1.23456789, "SELL"),
        ):
            with self.subTest(side=expected_side):
                self.position.get_amount.return_value = current
                order = self.context.order_target(
                    target_symbol="BTC", target_amount=target,
                    price=10, precision=6,
                )
                self.assertEqual(order["amount"], 1.234567)
                self.assertEqual(order["order_side"], expected_side)
        self.context._blotter.reset_mock()
        self.position.get_amount.return_value = 1
        self.assertIsNone(self.context.order_target(
            target_symbol="BTC", target_amount=1.0000001,
            price=10, precision=6,
        ))
        self.context._blotter.place_order.assert_not_called()

    def test_target_value_and_percentage_helpers(self):
        self.position.get_amount.return_value = 0
        for method, sizing in (
            ("order_target_value", {"target_value": 12.3456789}),
            ("order_target_percent", {"target_percent": 1.23456789}),
        ):
            with self.subTest(method=method):
                order = getattr(self.context, method)(
                    target_symbol="BTC", price=10, precision=6, **sizing
                )
                self.assertEqual(order["amount"], 1.234567)

    def test_close_position_rounds_before_submission(self):
        self.context.close_position(self.position, precision=6, price=10)
        order = self.context._blotter.place_order.call_args.args[0]
        self.assertEqual(order["amount"], 1.234567)

    def test_close_position_rejects_dust_before_canceling_orders(self):
        self.position.get_amount.return_value = 1e-7
        with self.assertRaisesRegex(
            OperationalException, "zero after rounding"
        ):
            self.context.close_position(self.position, precision=6, price=10)
        self.context.order_service.get_all.assert_not_called()
        self.context._blotter.cancel_order.assert_not_called()
        self.context._blotter.place_order.assert_not_called()

    def test_close_trade_rounds_after_clamping_to_position(self):
        self.position.get_amount.return_value = 1.2345678
        self.trade.available_amount = 2
        self.context.close_trade(self.trade, precision=6)
        order = self.context._blotter.place_order.call_args.args[0]
        self.assertEqual(order["amount"], 1.234567)

    def test_close_trade_rejects_dust_before_canceling_mirror_orders(self):
        self.trade.available_amount = 1e-7
        with self.assertRaisesRegex(
            OperationalException, "zero after rounding"
        ):
            self.context.close_trade(self.trade, precision=6)
        self.context.order_service \
            .cancel_mirror_orders_for_trade.assert_not_called()
        self.context._blotter.place_order.assert_not_called()
