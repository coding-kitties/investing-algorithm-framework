from investing_algorithm_framework import OrderSide, OrderType, OrderStatus
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A, SYMBOL_A_PRICE


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self) -> None:
        order = self.algo_app.algorithm\
            .create_limit_sell_order("test", SYMBOL_A, SYMBOL_A_PRICE, 10)

        self.assertEqual(order.trading_symbol, SYMBOL_A)
        self.assertIsNotNone(order.amount)
        self.assertIsNotNone(order.amount_trading_symbol)
        self.assertEqual(order.amount, 10)
        self.assertEqual(order.amount_trading_symbol, 100)
        self.assertIsNotNone(order.price)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNone(order.status)
        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.LIMIT.equals(order.order_type))

    def test_with_execution(self) -> None:
        order = self.algo_app.algorithm \
            .create_limit_buy_order(
            "test", SYMBOL_A, SYMBOL_A_PRICE, 10, execute=True
        )

        order.set_executed()

        self.assertEqual(order.position.amount, 10)
        self.assertEqual(order.position.cost, 10 * SYMBOL_A_PRICE)

        order = self.algo_app.algorithm\
            .create_limit_sell_order(
                "test", SYMBOL_A, SYMBOL_A_PRICE, 10, execute=True
            )

        self.assertEqual(order.trading_symbol, SYMBOL_A)
        self.assertIsNotNone(order.amount)
        self.assertIsNotNone(order.amount_trading_symbol)
        self.assertEqual(order.amount, 10)
        self.assertEqual(order.amount_trading_symbol, 100)
        self.assertIsNotNone(order.price)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNotNone(order.status)
        self.assertTrue(OrderStatus.PENDING.equals(order.status))
        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.LIMIT.equals(order.order_type))

        self.assertEqual(10, order.position.amount)
        self.assertEqual(100, order.position.cost)

        order.set_executed()


        self.assertEqual(0, order.position.amount)
        self.assertEqual(0, order.position.cost)
