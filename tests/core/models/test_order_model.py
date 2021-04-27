from tests.resources import TestBase
from investing_algorithm_framework.core.models import Order, OrderType


class TestOrderModel(TestBase):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()
        self.algorithm_context.add_data_provider(self.data_provider)
        self.algorithm_context.add_portfolio_manager(self.portfolio_manager)
        self.algorithm_context.add_order_executor(self.order_executor)

        for i in range(0, 10):
            order = Order(
                trading_pair="DOT/UDST",
                price=10,
                amount=10 * i,
                order_type=OrderType.BUY.value
            )

            order.save()

    def test_creation(self):
        self.assertEqual(10, Order.query.count())

    def test_deleting(self):
        for order in Order.query.all():
            order.delete()

        self.assertEqual(0, Order.query.count())

    def test_updating(self):
        self.assertEqual(0, Order.query.filter_by(completed=True).count())

        for order in Order.query.all():
            order.completed = True
            order.save()

        self.assertEqual(10, Order.query.count())
        self.assertEqual(10, Order.query.filter_by(completed=True).count())
