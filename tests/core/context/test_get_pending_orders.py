from investing_algorithm_framework import PortfolioManager, OrderExecutor, \
    Order, OrderStatus
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A_PRICE, SYMBOL_A


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def test(self) -> None:
        self.create_buy_order(
            10,
            SYMBOL_A,
            SYMBOL_A_PRICE,
            self.algo_app.algorithm.get_portfolio_manager()
        )

        orders = self.algo_app.algorithm\
            .get_pending_orders("test")

        self.assertIsNotNone(
            len(orders), Order.query.filter_by(status=OrderStatus.PENDING.value).count()
        )
