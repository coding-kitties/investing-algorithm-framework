from investing_algorithm_framework.core.models import Order, OrderSide, \
    OrderType, OrderStatus
from investing_algorithm_framework import OperationalException
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(TestOrderModel, self).setUp()
        self.order = Order(
            reference_id=1,
            status=OrderStatus.PENDING.value,
            type=OrderType.LIMIT.value,
            side=OrderSide.SELL.value,
            amount_trading_symbol=10,
            price=10,
            target_symbol=self.TARGET_SYMBOL_A,
            trading_symbol="USDT"
        )

    def test_get_reference_id(self):
        self.assertIsNotNone(self.order.get_reference_id())

    def test_get_target_symbol(self):
        self.assertIsNotNone(self.order.get_target_symbol())

    def test_get_trading_symbol(self):
        self.assertIsNotNone(self.order.get_trading_symbol())

    def test_get_amount_of_trading_symbol(self):
        self.assertIsNotNone(self.order.get_amount_trading_symbol())

    def test_get_amount_of_target_symbol(self):
        self.assertIsNotNone(self.order.get_amount_target_symbol())

    def test_get_initial_price(self):
        self.order.initial_price = 10
        self.assertIsNotNone(self.order.get_initial_price())

    def test_get_price(self):
        self.assertIsNotNone(self.order.get_price())

    def test_get_closing_price(self):
        self.order.closing_price = 10
        self.assertIsNotNone(self.order.get_closing_price())

    def test_get_side(self):
        self.assertIsNotNone(self.order.get_side())

    def test_get_status(self):
        self.assertIsNotNone(self.order.get_status())

    def test_get_type(self):
        self.assertIsNotNone(self.order.get_type())

    def test_from_dict_pending_limit_order_buy(self):
        order = Order.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "PENDING",
                "price": 10,
                "type": "LIMIT",
                "side": "BUY"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

    def test_from_dict_successful_limit_order_buy(self):
        order = Order.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "SUCCESS",
                "price": 10,
                "initial_price": 10,
                "type": "LIMIT",
                "side": "BUY"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

        with self.assertRaises(OperationalException):
            Order.from_dict(
                {
                    "reference_id": 10493,
                    "target_symbol": "DOT",
                    "trading_symbol": "USDT",
                    "amount_target_symbol": 40,
                    "status": "SUCCESS",
                    "price": 10,
                    "type": "LIMIT",
                    "side": "BUY"
                }
            )

    def test_from_dict_closed_limit_order_buy(self):
        order = Order.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "CLOSED",
                "initial_price": 10,
                "closing_price": 11,
                "type": "LIMIT",
                "side": "BUY"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_closing_price())
        self.assertIsNotNone(order.get_initial_price())

        with self.assertRaises(OperationalException):
            Order.from_dict(
                {
                    "reference_id": 10493,
                    "target_symbol": "DOT",
                    "trading_symbol": "USDT",
                    "amount_target_symbol": 40,
                    "status": "CLOSED",
                    "price": 10,
                    "initial_price": 10,
                    "type": "LIMIT",
                    "side": "BUY"
                }
            )
