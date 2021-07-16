from tests.resources import TestBase
from investing_algorithm_framework.core.models import Order, Position, db, \
    OrderSide, Portfolio
from investing_algorithm_framework.core.exceptions import OperationalException


class Test(TestBase):

    def setUp(self) -> None:
        super(Test, self).setUp()
        self.portfolio = Portfolio(
            base_currency="USDT",
            broker="BINANCE",
            unallocated=1000
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
                order_side=OrderSide.BUY.value
            )
            order.save(db)
            self.portfolio.add_buy_order(order)

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
            order_side=OrderSide.BUY.value
        )
        order.save(db)
        self.portfolio.add_buy_order(order)

        self.assertEqual(
            float(1000) - (10 * 5),
            float(self.portfolio.unallocated)
        )

    def test_buy_order_creation_unallocated(self):
        self.assertEqual(
            float(1000),
            float(self.portfolio.unallocated)
        )

        order = Order(
            target_symbol="BTC",
            trading_symbol="USDT",
            price=1100,
            amount=10,
            order_side=OrderSide.BUY.value
        )
        order.save(db)

        with self.assertRaises(OperationalException):
            self.portfolio.add_buy_order(order)

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
            order_side=OrderSide.BUY.value
        )
        order.save(db)
        self.portfolio.add_buy_order(order)

        self.assertEqual(
            float(1000) - (10 * 5),
            float(self.portfolio.unallocated)
        )

        order = Order(
            target_symbol="USDT",
            trading_symbol="BTC",
            price=5,
            amount=10,
            order_side=OrderSide.SELL.value
        )
        order.save(db)
        self.portfolio.add_sell_order(order)
        self.assertEqual(float(1000), float(self.portfolio.unallocated))

    def test_get_positions(self):
        # Create some orders and positions
        for i in range(0, 5):
            order = Order(
                target_symbol="BTC",
                trading_symbol="USDT",
                price=5,
                amount=10,
                order_side=OrderSide.BUY.value
            )
            order.save(db)
            self.portfolio.add_buy_order(order)

        self.assertEqual(1, len(self.portfolio.positions))

        # Create some orders and positions
        for i in range(0, 5):
            order = Order(
                target_symbol="ETH",
                trading_symbol="USDT",
                price=5,
                amount=10,
                order_side=OrderSide.BUY.value
            )
            order.save(db)
            self.portfolio.add_buy_order(order)

        self.assertEqual(2, len(self.portfolio.positions))
