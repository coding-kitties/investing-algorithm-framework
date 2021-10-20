from investing_algorithm_framework import OrderSide, OrderType, OrderStatus
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A, SYMBOL_A_PRICE


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self) -> None:
        order = self.algo_app.algorithm\
            .create_market_buy_order("test", SYMBOL_A, 10)

        portfolio = self.algo_app.algorithm.get_portfolio_manager()\
            .get_portfolio()

        self.assertIsNone(order.amount)
        self.assertIsNotNone(order.amount_trading_symbol)
        self.assertEqual(order.amount_trading_symbol, 10)
        self.assertEqual(order.trading_symbol, portfolio.trading_symbol)
        self.assertIsNone(order.price)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNone(order.status)
        self.assertTrue(OrderSide.BUY.equals(order.order_side))
        self.assertTrue(OrderType.MARKET.equals(order.order_type))

    def test_with_execution(self) -> None:
        order = self.algo_app.algorithm\
            .create_market_buy_order(
                "test", SYMBOL_A, 10, execute=True
            )

        portfolio = self.algo_app.algorithm.get_portfolio_manager()\
            .get_portfolio()

        self.assertIsNone(order.amount)
        self.assertIsNotNone(order.amount_trading_symbol)
        self.assertEqual(10, order.amount_trading_symbol)
        self.assertEqual(order.trading_symbol, portfolio.trading_symbol)
        self.assertIsNone(order.price)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNotNone(order.status)
        self.assertTrue(OrderStatus.PENDING.equals(order.status))
        self.assertTrue(OrderSide.BUY.equals(order.order_side))
        self.assertTrue(OrderType.MARKET.equals(order.order_type))

        self.assertEqual(order.position.amount, 0)
        self.assertEqual(order.position.cost, 0)

        order.price = SYMBOL_A_PRICE
        order.amount = 10

        order.set_executed()

        self.assertEqual(order.position.amount, 10)
        self.assertEqual(order.position.cost, 10 * SYMBOL_A_PRICE)
        self.assertEqual(order.amount_trading_symbol, 10)
