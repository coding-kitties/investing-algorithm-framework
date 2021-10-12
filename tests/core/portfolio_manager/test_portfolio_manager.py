from investing_algorithm_framework import OrderSide, OrderType
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A, SYMBOL_A_PRICE


class Test(TestOrderAndPositionsObjectsMixin, TestBase):

    def test_id(self):
        self.assertIsNotNone(self.algo_app.algorithm.get_portfolio_manager())

    def test_initialize(self):
        self.assertTrue(
            self.algo_app.algorithm.get_portfolio_manager().initialize_has_run
        )

    def test_create_buy_order(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertIsNotNone(order)

        self.assertTrue(OrderSide.BUY.equals(order.order_side))
        self.assertTrue(OrderType.LIMIT.equals(order.order_type))
        self.assertIsNone(order.order_reference)
        self.assertEqual(1, order.amount)
        self.assertEqual(SYMBOL_A_PRICE, order.price)
        self.assertIsNone(order.status)
        self.assertIsNone(order.executed_at)

    def test_create_sell_order(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertIsNotNone(order)

        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.LIMIT.equals(order.order_type))
        self.assertIsNone(order.order_reference)
        self.assertEqual(1, order.amount)
        self.assertEqual(SYMBOL_A_PRICE, order.price)
        self.assertIsNone(order.status)
        self.assertIsNone(order.executed_at)

    def test_get_portfolio(self):
        portfolio = self.algo_app.algorithm.get_portfolio_manager().get_portfolio()
        self.assertIsNotNone(portfolio)

    def test_get_orders(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        orders = portfolio_manager.get_orders()
        self.assertEqual(0, len(orders))

        orders = portfolio_manager.get_orders(lazy=True)
        self.assertEqual(0, orders.count())

    def test_get_positions(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        positions = portfolio_manager.get_positions()
        self.assertEqual(0, len(positions))

        positions = portfolio_manager.get_positions(lazy=True)
        self.assertEqual(0, positions.count())

    def test_get_pending_orders(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order)
        order.set_pending()

        self.assertEqual(1, len(portfolio_manager.get_pending_orders()))

        self.assertEqual(
            1, portfolio_manager.get_pending_orders(lazy=True).count()
        )
