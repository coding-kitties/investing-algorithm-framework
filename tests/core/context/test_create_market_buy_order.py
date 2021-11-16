from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self) -> None:
        order = self.algo_app.algorithm\
            .create_market_buy_order(
                identifier="test",
                symbol=self.TARGET_SYMBOL_A,
                amount_trading_symbol=10
            )

        self.assertIsNone(order.amount)
        self.assert_is_market_order(order)

    def test_with_execution(self) -> None:
        order = self.algo_app.algorithm\
            .create_market_buy_order(
                identifier="test",
                symbol=self.TARGET_SYMBOL_A,
                amount_trading_symbol=10,
                execute=True
            )

        self.assertIsNone(order.amount)
        self.assert_is_market_order(order)

        self.assertEqual(order.position.amount, 0)
        self.assertEqual(order.position.cost, 0)

        order.set_executed(amount=10, price=self.BASE_SYMBOL_A_PRICE)

        self.assertEqual(order.position.amount, 10)
        self.assertEqual(order.position.cost, 10 * self.BASE_SYMBOL_A_PRICE)
        self.assertEqual(order.amount_trading_symbol, 10)

        self.assert_is_market_order(order, True)
