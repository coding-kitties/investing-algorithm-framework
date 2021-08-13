from investing_algorithm_framework import PortfolioManager, OrderExecutor, \
    Order, db
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class PortfolioManagerOne(PortfolioManager):
    trading_currency = "USDT"
    identifier = "KRAKEN"

    def get_initial_unallocated_size(self) -> float:
        return 1000


class OrderExecutorOne(OrderExecutor):
    identifier = "KRAKEN"

    def execute_limit_order(self, order: Order, algorithm_context,
                            **kwargs) -> bool:
        return order

    def execute_market_order(self, order: Order, algorithm_context,
                             **kwargs) -> bool:
        return order

    def update_order_status(self, order: Order, algorithm_context,
                            **kwargs) -> bool:
        order.executed = True
        db.session.commit()


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self) -> None:
        super(Test, self).setUp()
        self.portfolio_manager_one = PortfolioManagerOne()
        self.order_executor = OrderExecutorOne()
        self.algo_app.algorithm.add_portfolio_manager(
            self.portfolio_manager_one
        )
        self.algo_app.algorithm.add_order_executor(
            self.order_executor
        )
        self.algo_app.algorithm.start()
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.algo_app.algorithm.start()

    def test(self) -> None:
        orders = self.algo_app.algorithm\
            .get_pending_orders("KRAKEN")

        self.assertIsNotNone(
            len(orders), Order.query.filter_by(executed=False).count()
        )
