from investing_algorithm_framework.core.models import Order, OrderSide, \
    OrderType, OrderStatus
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(TestOrderModel, self).setUp()
        self.order = Order(
            id=1,
            reference_id=1,
            status=OrderStatus.PENDING.value,
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_trading_symbol=10,
            price=10,
            target_symbol=self.TARGET_SYMBOL_A,
            trading_symbol="USDT"
        )

    def test_get_id(self):
        self.assertIsNotNone(self.order.get_id())

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
