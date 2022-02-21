from investing_algorithm_framework.core.models import Order, OrderSide, \
    OrderType, OrderStatus, Position
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestPositionModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(TestPositionModel, self).setUp()
        self.position = Position(
            symbol=self.TARGET_SYMBOL_A,
            amount=10
        )

    def test_get_symbol(self):
        self.assertIsNotNone(self.position.get_symbol())

    def test_get_amount(self):
        self.assertIsNotNone(self.position.get_amount())

    def test_get_orders(self):
        orders = [Order(
            id=1,
            reference_id=1,
            status=OrderStatus.PENDING.value,
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_trading_symbol=10,
            price=10,
            target_symbol=self.TARGET_SYMBOL_A,
            trading_symbol="USDT"
        )]
        self.position.orders = orders
        self.assertIsNotNone(self.position.get_orders())
