from investing_algorithm_framework import PortfolioManager, Order, \
    Position, OrderSide, Portfolio
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class MyPortfolioManagerOne(PortfolioManager):
    identifier = "KRAKEN"
    trading_currency = "USDT"

    def get_initial_unallocated_size(self) -> float:
        return 50000


class MyPortfolioManagerTwo(PortfolioManager):
    identifier = "BINANCE"
    trading_currency = "BUSD"

    def get_initial_unallocated_size(self) -> float:
        return 50000


class Test(TestOrderAndPositionsObjectsMixin, TestBase):

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

    def tearDown(self):
        self.algo_app.algorithm._portfolio_managers = {}
        super(Test, self).tearDown()

    def test_id(self):
        self.assertIsNotNone(self.portfolio_manager_one.identifier)
        self.assertIsNotNone(self.portfolio_manager_one.get_id())
        self.portfolio_manager_one.identifier = None

        with self.assertRaises(AssertionError):
            self.portfolio_manager_one.get_id()

    def test_initialize(self):
        pass

    def test_create_buy_order(self):
        order = self.portfolio_manager_one.create_buy_order(
            symbol=self.TICKERS[0],
            amount=10,
            price=10
        )

        self.assertEqual(order.target_symbol, self.TICKERS[0])
        self.assertEqual(
            order.trading_symbol, self.portfolio_manager_one.trading_currency
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
            order.target_symbol, self.portfolio_manager_one.trading_currency
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
                .filter_by(identifier=self.portfolio_manager_one.identifier)
                .first()
        )

    def test_get_orders(self):
        my_portfolio_manager_one = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerOne.identifier)

        orders = my_portfolio_manager_one.get_orders()
        self.assertEqual(20, len(orders))

        my_portfolio_manager_two = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerTwo.identifier)

        orders = my_portfolio_manager_two.get_orders()
        self.assertEqual(20, len(orders))

        self.assertEqual(40, Order.query.count())

    def test_get_positions(self):
        my_portfolio_manager_one = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerOne.identifier)

        positions = my_portfolio_manager_one.get_positions()

        self.assertEqual(
            Position.query
                .filter_by(
                    portfolio=self.portfolio_manager_one.get_portfolio()
                )
                .count(),
            len(positions)
        )

        my_portfolio_manager_two = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerTwo.identifier)

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
            .get_portfolio_manager(MyPortfolioManagerOne.identifier)

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
