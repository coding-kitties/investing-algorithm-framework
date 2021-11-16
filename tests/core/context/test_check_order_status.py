from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()

        self.start_algorithm()

        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.create_buy_order(
            1,
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE,
            portfolio_manager
        )

    def test(self) -> None:
        self.algo_app.algorithm.check_order_status("test")
        self.assertEqual(
            0, len(self.algo_app.algorithm.get_pending_orders("test"))
        )
