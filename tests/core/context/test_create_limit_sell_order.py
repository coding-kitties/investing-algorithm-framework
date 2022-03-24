from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework import Position


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self) -> None:
        self.algo_app.algorithm.add_position(
            Position(target_symbol=self.TARGET_SYMBOL_A, amount=10)
        )
        order = self.algo_app.algorithm\
            .create_limit_sell_order(
                target_symbol=self.TARGET_SYMBOL_A,
                price=self.BASE_SYMBOL_A_PRICE,
                amount_target_symbol=10
            )

        self.assert_is_limit_order(order)

    def test_with_execution(self) -> None:
        self.algo_app.algorithm.add_position(
            Position(target_symbol=self.TARGET_SYMBOL_A, amount=10)
        )
        order = self.algo_app.algorithm \
            .create_limit_sell_order(
                target_symbol=self.TARGET_SYMBOL_A,
                price=self.BASE_SYMBOL_A_PRICE,
                amount_target_symbol=10,
                execute=True
        )

        self.assert_is_limit_order(order, executed=True)
