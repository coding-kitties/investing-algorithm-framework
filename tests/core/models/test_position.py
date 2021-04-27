from tests.resources import TestBase
from investing_algorithm_framework.core.models import Order, OrderType, \
    Position, db


class TestPosition(TestBase):

    def setUp(self) -> None:
        super(TestPosition, self).setUp()
        self.algorithm_context.add_data_provider(self.data_provider)
        self.algorithm_context.add_portfolio_manager(self.portfolio_manager)
        self.algorithm_context.add_order_executor(self.order_executor)

        self.position = Position("DOT")
        self.position.save()

        for i in range(0, 10):
            order = Order(
                trading_pair="DOT/UDST",
                price=10,
                amount=10 * i,
                order_type=OrderType.BUY.value
            )

            order.save()
            self.position.orders.append(order)

        db.session.commit()

    def test_creation(self):
        self.assertEqual(
            10, Order.query.filter_by(position=self.position).count()
        )
        self.assertEqual(
            1, Position.query.count()
        )

    def test_deleting(self):
        self.position.delete()

        self.assertEqual(0, Order.query.count())
        self.assertEqual(0, Position.query.count())
