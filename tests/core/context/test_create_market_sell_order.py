from investing_algorithm_framework import OrderSide, OrderType
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self) -> None:
        order = self.algo_app.algorithm\
            .create_market_sell_order(
                identifier="test",
                symbol=self.TARGET_SYMBOL_A,
                amount_target_symbol=10
            )

        self.assertIsNone(order.amount_trading_symbol)
        self.assertEqual(order.target_symbol, self.TARGET_SYMBOL_A)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNone(order.status)
        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.MARKET.equals(order.order_type))

    def test_with_execution(self) -> None:
        order = self.algo_app.algorithm \
            .create_market_buy_order(
                identifier="test",
                symbol=self.TARGET_SYMBOL_A,
                amount_trading_symbol=10
            )

        portfolio = self.algo_app.algorithm\
            .get_portfolio_manager()\
            .get_portfolio()

        portfolio.add_order(order)
        order.set_pending()
        order.set_executed(amount=10, price=self.BASE_SYMBOL_A_PRICE)

        self.assertEqual(order.amount_target_symbol, 10)
        self.assertEqual(order.position.cost, 10 * self.BASE_SYMBOL_A_PRICE)
        self.assertEqual(order.amount_trading_symbol, 10)

        self.assert_is_market_order(order, True)
