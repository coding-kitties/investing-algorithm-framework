from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework import PortfolioManager, OrderExecutor, \
    Order, db, OrderSide, OrderType


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
        order = self.algo_app.algorithm\
            .create_limit_sell_order("KRAKEN", "BTC", 10, 10)

        self.assertIsNotNone(order.amount)
        self.assertIsNotNone(order.price)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertFalse(order.executed)
        self.assertFalse(order.successful)
        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.LIMIT.equals(order.order_type))
