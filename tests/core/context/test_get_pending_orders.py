from investing_algorithm_framework import Order, OrderStatus
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self) -> None:
        self.create_buy_order(
            10,
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE,
            self.algo_app.algorithm.get_portfolio_manager()
        )

        orders = self.algo_app.algorithm\
            .get_pending_orders("test")

        self.assertIsNotNone(
            len(orders), Order.query.filter_by(status=OrderStatus.PENDING.value).count()
        )
