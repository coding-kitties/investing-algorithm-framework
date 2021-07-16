from tests.resources import TestBase
from investing_algorithm_framework.core.models import Order, Position, db, \
    OrderSide


class TestPosition(TestBase):

    def setUp(self) -> None:
        super(TestPosition, self).setUp()

        self.position = Position("DOT")
        self.position.save(db)

        for i in range(0, 10):
            order = Order(
                target_symbol="DOT",
                trading_symbol="USDT",
                price=10,
                amount=10 * i,
                order_side=OrderSide.BUY.value
            )

            order.save(db)
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
        self.assertEqual(
            10, Order.query.filter_by(position=self.position).count()
        )
        self.assertEqual(
            1, Position.query.count()
        )

        self.position.delete(db)

        self.assertEqual(0, Order.query.count())
        self.assertEqual(0, Position.query.count())
