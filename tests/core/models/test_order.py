from tests.resources import TestBase
from investing_algorithm_framework.core.models import Order, OrderSide, db


class TestOrderModel(TestBase):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()

        for i in range(0, 10):
            order = Order(
                target_symbol="DOT",
                trading_symbol="USDT",
                price=10,
                amount=10 * i,
                order_side=OrderSide.BUY.value
            )

            order.save(db)

    def test_creation(self):
        self.assertEqual(10, Order.query.count())

    def test_deleting(self):
        for order in Order.query.all():
            order.delete(db)

        self.assertEqual(0, Order.query.count())

    def test_updating(self):
        self.assertEqual(0, Order.query.filter_by(completed=True).count())

        for order in Order.query.all():
            order.completed = True
            order.save(db)

        self.assertEqual(10, Order.query.count())
        self.assertEqual(10, Order.query.filter_by(completed=True).count())
