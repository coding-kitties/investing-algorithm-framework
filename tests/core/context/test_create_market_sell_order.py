from investing_algorithm_framework import OrderSide, OrderType, OrderStatus
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A, SYMBOL_A_PRICE


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self) -> None:
        order = self.algo_app.algorithm\
            .create_market_sell_order("test", SYMBOL_A, 10)

        self.assertIsNotNone(order.amount_trading_symbol)
        self.assertEqual(order.trading_symbol, SYMBOL_A)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNone(order.status)
        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.MARKET.equals(order.order_type))

    def test_with_execution(self) -> None:
        order = self.algo_app.algorithm \
            .create_market_buy_order("test", SYMBOL_A, 10, execute=True)

        order.price = SYMBOL_A_PRICE
        order.amount = 10
        order.set_executed()

        self.assertEqual(order.position.amount, 10)
        self.assertEqual(order.position.cost, 10 * SYMBOL_A_PRICE)
        self.assertEqual(order.amount_trading_symbol, 10)

        order = self.algo_app.algorithm\
            .create_market_sell_order(
                "test", SYMBOL_A, 10, execute=True
            )

        self.assertIsNotNone(order.amount_trading_symbol)
        self.assertEqual(order.trading_symbol, SYMBOL_A)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNotNone(order.status)
        self.assertTrue(OrderStatus.PENDING.equals(order.status))
        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.MARKET.equals(order.order_type))

        self.assertEqual(order.position.amount, 10)
        self.assertEqual(order.position.cost, 10 * SYMBOL_A_PRICE)
        self.assertEqual(order.amount_trading_symbol, 10)

        order.price = SYMBOL_A_PRICE
        order.amount = 10

        order.set_executed()
