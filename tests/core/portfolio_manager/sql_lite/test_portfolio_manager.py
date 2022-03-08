from investing_algorithm_framework import OrderSide, OrderType, OrderStatus, \
    Position, Portfolio, OperationalException
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class Test(TestOrderAndPositionsObjectsMixin, TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test_identifier(self):
        portfolio_manager = self.algo_app.algorithm\
            .get_portfolio_manager('sqlite')
        self.assertIsNotNone(portfolio_manager.get_identifier())
        self.assertEqual("sqlite", portfolio_manager.get_identifier())

    def test_get_trading_symbol(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')
        self.assertIsNotNone(portfolio_manager
                             .get_trading_symbol(self.algo_app.algorithm))
        self.assertEqual("USDT", portfolio_manager
                         .get_trading_symbol(self.algo_app.algorithm))

    def test_get_positions(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')

        self.assertIsNotNone(
            portfolio_manager.get_positions(self.algo_app.algorithm)
        )

        positions = portfolio_manager.get_positions(self.algo_app.algorithm)
        self.assertTrue(isinstance(positions[0], Position))

    def test_get_portfolio(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')

        self.assertIsNotNone(
            portfolio_manager.get_portfolio(self.algo_app.algorithm)
        )

        portfolio = portfolio_manager.get_portfolio(self.algo_app.algorithm)
        self.assertTrue(isinstance(portfolio, Portfolio))

    def test_get_orders(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')

        self.assertIsNotNone(
            portfolio_manager.get_orders(self.algo_app.algorithm)
        )

    def test_initialize(self):
        self.assertTrue(
            self.algo_app.algorithm.get_portfolio_manager().initialize_has_run
        )

    def test_create_limit_buy_order(self):
        portfolio_manager = self.algo_app.algorithm\
            .get_portfolio_manager('sqlite')

        order = portfolio_manager.create_order(
            type=OrderType.LIMIT.value,
            side=OrderSide.BUY.value,
            amount_target_symbol=1,
            target_symbol=self.TARGET_SYMBOL_A,
            price=self.BASE_SYMBOL_A_PRICE,
            algorithm_context=None
        )

        self.assertIsNotNone(order)
        self.assert_is_limit_order(order)

    def test_add_order(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')

        order = portfolio_manager.create_order(
            type=OrderType.LIMIT.value,
            side=OrderSide.BUY.value,
            amount_target_symbol=1,
            target_symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            algorithm_context=None
        )
        order.set_status(OrderStatus.SUCCESS)
        order.set_reference_id(2)
        order.set_initial_price(self.get_price(self.TARGET_SYMBOL_A).price)
        portfolio_manager.add_order(order, algorithm_context=None)
        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)
        self.assertIsNotNone(position)
        self.assertEqual(1, len(portfolio.get_orders()))
        self.assertEqual(2, len(portfolio.get_positions()))
        self.assertEqual(1, position.get_amount())

    def test_add_sell_order(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')

        order = portfolio_manager.create_order(
            type=OrderType.LIMIT.value,
            side=OrderSide.BUY.value,
            amount_target_symbol=1,
            target_symbol=self.TARGET_SYMBOL_A,
            price=self.BASE_SYMBOL_A_PRICE,
            algorithm_context=None
        )
        order.set_status(OrderStatus.SUCCESS)
        order.set_reference_id(2)
        order.set_initial_price(self.get_price(self.TARGET_SYMBOL_A).price)
        portfolio_manager.add_order(order, algorithm_context=None)
        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        self.assertEqual(1, len(portfolio.get_orders()))
        self.assertEqual(2, len(portfolio.get_positions()))
        position = portfolio.get_position(self.TARGET_SYMBOL_A)
        self.assertIsNotNone(position)
        self.assertNotEqual(0, position.get_amount())

        order = portfolio_manager.create_order(
            type=OrderType.LIMIT.value,
            side=OrderSide.SELL.value,
            amount_target_symbol=1,
            target_symbol=self.TARGET_SYMBOL_A,
            price=self.BASE_SYMBOL_A_PRICE,
            algorithm_context=None
        )
        order.set_reference_id(3)
        order.set_status(OrderStatus.SUCCESS)
        order.set_initial_price(self.get_price(self.TARGET_SYMBOL_A).price)
        portfolio_manager.add_order(order, algorithm_context=None)
        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)
        self.assertIsNone(position)

    def test_add_buy_order_larger_then_unallocated(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')

        with self.assertRaises(OperationalException) as exc:
            portfolio_manager.create_order(
                type=OrderType.LIMIT.value,
                side=OrderSide.BUY.value,
                amount_target_symbol=10000,
                target_symbol=self.TARGET_SYMBOL_A,
                price=self.BASE_SYMBOL_A_PRICE,
                algorithm_context=None
            )

    def test_add_sell_order_without_position(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')

        with self.assertRaises(OperationalException):
            portfolio_manager.create_order(
                type=OrderType.LIMIT.value,
                side=OrderSide.SELL.value,
                amount_target_symbol=10000,
                target_symbol=self.TARGET_SYMBOL_A,
                price=self.BASE_SYMBOL_A_PRICE,
                algorithm_context=None
            )

    def test_add_sell_order_larger_then_position(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('sqlite')

        order = portfolio_manager.create_order(
            type=OrderType.LIMIT.value,
            side=OrderSide.BUY.value,
            amount_target_symbol=1,
            target_symbol=self.TARGET_SYMBOL_A,
            price=self.BASE_SYMBOL_A_PRICE,
            algorithm_context=None
        )
        order.set_status(OrderStatus.SUCCESS)
        order.set_reference_id(2)
        order.set_initial_price(self.get_price(self.TARGET_SYMBOL_A).price)
        portfolio_manager.add_order(order, algorithm_context=None)

        with self.assertRaises(OperationalException):
            portfolio_manager.create_order(
                type=OrderType.LIMIT.value,
                side=OrderSide.SELL.value,
                amount_target_symbol=10000,
                target_symbol=self.TARGET_SYMBOL_A,
                price=self.BASE_SYMBOL_A_PRICE,
                algorithm_context=None
            )
