from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework import Position


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self) -> None:
        self.algo_app.algorithm.add_position(
            Position(symbol=self.TARGET_SYMBOL_A, amount=10)
        )
        order = self.algo_app.algorithm\
            .create_market_sell_order(
                target_symbol=self.TARGET_SYMBOL_A,
                amount_target_symbol=10
            )

        self.assert_is_market_order(order)

    def test_with_execution(self) -> None:
        self.algo_app.algorithm.add_position(
            Position(symbol=self.TARGET_SYMBOL_A, amount=10)
        )
        order = self.algo_app.algorithm \
            .create_market_sell_order(
                target_symbol=self.TARGET_SYMBOL_A,
                amount_target_symbol=10,
                execute=True
        )
        order.set_price(self.get_price(self.TARGET_SYMBOL_A).price)

        self.assert_is_market_order(order, executed=True)
