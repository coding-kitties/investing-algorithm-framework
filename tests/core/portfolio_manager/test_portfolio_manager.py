from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework import TimeUnit, PortfolioManager, Order, \
    AlgorithmContext, Position, OrderSide, Portfolio


class MyPortfolioManagerOne(PortfolioManager):
    broker = "KRAKEN"
    base_currency = "USDT"

    def get_initial_unallocated_size(self) -> float:
        return 50000


class MyPortfolioManagerTwo(PortfolioManager):
    broker = "BINANCE"
    base_currency = "BUSD"

    def get_initial_unallocated_size(self) -> float:
        return 50000


def worker_one(algorithm: AlgorithmContext):
    pass


def worker_two(algorithm: AlgorithmContext):
    pass


class Test(TestOrderAndPositionsObjectsMixin, TestBase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.algo_app.algorithm.schedule(worker_one, None, TimeUnit.SECONDS, 1)
        cls.algo_app.algorithm.schedule(worker_two, None, TimeUnit.SECONDS, 1)

    def setUp(self) -> None:
        super(Test, self).setUp()
        self.portfolio_manager_one = MyPortfolioManagerOne()
        self.portfolio_manager_two = MyPortfolioManagerTwo()
        self.algo_app.algorithm.add_portfolio_manager(
            self.portfolio_manager_one
        )
        self.algo_app.algorithm.add_portfolio_manager(
            self.portfolio_manager_two
        )
        self.algo_app.algorithm.start()
        self.create_test_objects(self.portfolio_manager_one)
        self.create_test_objects(self.portfolio_manager_two)

    def test_create_buy_order(self):
        order = self.portfolio_manager_one.create_buy_order(
            symbol=self.TICKERS[0],
            amount=10,
            price=10
        )

        self.assertEqual(order.target_symbol, self.TICKERS[0])
        self.assertEqual(
            order.trading_symbol, self.portfolio_manager_one.base_currency
        )
        self.assertTrue(OrderSide.BUY.equals(order.order_side))
        self.assertEqual(order.amount, 10)
        self.assertEqual(order.price, 10)

    def test_create_sell_order(self):
        order = self.portfolio_manager_one.create_sell_order(
            symbol=self.TICKERS[0],
            amount=10,
            price=10
        )

        self.assertEqual(order.trading_symbol, self.TICKERS[0])
        self.assertEqual(
            order.target_symbol, self.portfolio_manager_one.base_currency
        )
        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertEqual(order.amount, 10)
        self.assertEqual(order.price, 10)

    def test_get_portfolio(self):
        portfolio = self.portfolio_manager_one.get_portfolio()
        self.assertIsNotNone(portfolio)
        self.assertEqual(
            portfolio,
            Portfolio.query\
                .filter_by(broker=self.portfolio_manager_one.broker)
                .first()
        )

    def test_portfolio_manager_retrieving(self) -> None:
        my_portfolio_manager_one = self.algo_app.algorithm\
            .get_portfolio_manager(MyPortfolioManagerOne.broker)

        self.assertTrue(
            my_portfolio_manager_one.broker, MyPortfolioManagerOne.broker
        )

        my_portfolio_manager_two = self.algo_app.algorithm\
            .get_portfolio_manager(MyPortfolioManagerTwo.broker)

        self.assertTrue(
            my_portfolio_manager_two.broker, MyPortfolioManagerTwo.broker
        )

    def test_get_orders(self):
        my_portfolio_manager_one = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerOne.broker)

        orders = my_portfolio_manager_one.get_orders()
        self.assertEqual(20, len(orders))

        my_portfolio_manager_two = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerTwo.broker)

        orders = my_portfolio_manager_two.get_orders()
        self.assertEqual(20, len(orders))

        self.assertEqual(40, Order.query.count())

    def test_get_positions(self):
        my_portfolio_manager_one = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerOne.broker)

        positions = my_portfolio_manager_one.get_positions()

        self.assertEqual(
            Position.query
                .filter_by(portfolio=self.portfolio_manager_one.get_portfolio())
                .count(),
            len(positions)
        )

        my_portfolio_manager_two = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerTwo.broker)

        positions = my_portfolio_manager_two.get_positions()

        self.assertEqual(
            Position.query
                .filter_by(
                    portfolio=self.portfolio_manager_two.get_portfolio()
                )
                .count(),
            len(positions)
        )

    def test_get_pending_orders(self):
        my_portfolio_manager_one = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerOne.broker)

        positions = my_portfolio_manager_one.get_positions(lazy=True)

        pending_orders = my_portfolio_manager_one.get_pending_orders(lazy=True)

        self.assertEqual(
            Order.query
                .filter_by(executed=False)
                .filter(Order.position_id.in_(
                    positions.with_entities(Position.id)
                ))
                .count(),
            pending_orders.count()
        )

        positions = my_portfolio_manager_one\
            .get_positions(symbol=self.TICKERS[0], lazy=True)
        pending_orders = my_portfolio_manager_one\
            .get_pending_orders(symbol=self.TICKERS[0], lazy=True)

        self.assertEqual(
            Order.query
                .filter(Order.position_id.in_(
                    positions.with_entities(Position.id)
                ))
                .count(),
            pending_orders.count()
        )
