from tests.resources import TestBase, random_string
from investing_algorithm_framework.core.models import Order, Position, db, \
    OrderSide, Portfolio, OrderType
from investing_algorithm_framework.core.exceptions import OperationalException


class Test(TestBase):

    def setUp(self) -> None:
        super(Test, self).setUp()
        self.portfolio = Portfolio(
            trading_symbol="USDT",
            identifier="BINANCE",
            unallocated=1000,
            market="BINANCE"
        )
        self.portfolio.save(db)

    def test_creation(self):
        self.assertEqual(1, Portfolio.query.count())

    def test_deleting(self):

        # Create some orders and positions
        for i in range(0, 5):
            order = Order(
                target_symbol="BTC",
                trading_symbol="USDT",
                price=5,
                amount=10,
                order_side=OrderSide.BUY.value,
                order_type=OrderType.LIMIT.value
            )
            order.save(db)
            self.portfolio.add_order(order)

        self.assertEqual(5, Order.query.count())
        self.assertEqual(1, Position.query.count())

        self.portfolio.delete(db)

        self.assertEqual(0, Order.query.count())
        self.assertEqual(0, Position.query.count())
        self.assertEqual(0, Portfolio.query.count())

    def test_buy_order_creation(self):
        self.assertEqual(
            float(1000),
            float(self.portfolio.unallocated)
        )

        order = Order(
            target_symbol="BTC",
            trading_symbol="USDT",
            price=5,
            amount=10,
            order_side=OrderSide.BUY.value,
            order_type=OrderType.LIMIT.value
        )
        order.save(db)
        self.portfolio.add_order(order)

        self.assertEqual(
            float(1000) - (10 * 5),
            float(self.portfolio.unallocated)
        )

    def test_buy_order_creation_larger_then_unallocated(self):
        self.assertEqual(
            float(1000),
            float(self.portfolio.unallocated)
        )

        order = Order(
            target_symbol="BTC",
            trading_symbol="USDT",
            price=1100,
            amount=10,
            order_side=OrderSide.BUY.value,
            order_type=OrderType.LIMIT.value
        )
        order.save(db)

        with self.assertRaises(OperationalException):
            self.portfolio.add_order(order)

    def test_sell_order_creation(self):
        self.assertEqual(
            float(1000),
            float(self.portfolio.unallocated)
        )

        order = Order(
            target_symbol="BTC",
            trading_symbol="USDT",
            price=5,
            amount=10,
            order_side=OrderSide.BUY.value,
            order_type=OrderType.LIMIT.value
        )
        order.save(db)
        self.portfolio.add_order(order)

        self.assertEqual(
            float(1000) - (10 * 5),
            float(self.portfolio.unallocated)
        )

        order.set_executed()

        order = Order(
            target_symbol="USDT",
            trading_symbol="BTC",
            price=5,
            amount=10,
            order_side=OrderSide.SELL.value,
            order_type=OrderType.LIMIT.value
        )
        order.save(db)
        self.portfolio.add_order(order)

        order.set_executed()
        self.assertEqual(float(1000), float(self.portfolio.unallocated))

    def test_get_positions(self):
        # Create some orders and positions
        for i in range(0, 5):
            order = Order(
                target_symbol="BTC",
                trading_symbol="USDT",
                price=5,
                amount=10,
                order_side=OrderSide.BUY.value,
                order_type=OrderType.LIMIT.value
            )
            order.save(db)
            self.portfolio.add_order(order)

        self.assertEqual(1, self.portfolio.positions.count())

        # Create some orders and positions
        for i in range(0, 5):
            order = Order(
                target_symbol="ETH",
                trading_symbol="USDT",
                price=5,
                amount=10,
                order_side=OrderSide.BUY.value,
                order_type=OrderType.LIMIT.value
            )
            order.save(db)
            self.portfolio.add_order(order)

        self.assertEqual(2, self.portfolio.positions.count())
