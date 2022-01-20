from investing_algorithm_framework import OrderExecutor, Order, OrderStatus, \
    SQLLitePortfolioManager, SQLLitePortfolio
from investing_algorithm_framework.core.models import db
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class OrderExecutorTestTwo(OrderExecutor):
    identifier = "testTwo"

    def execute_limit_order(self, order: Order, algorithm_context,
                            **kwargs) -> bool:
        pass

    def execute_market_order(self, order: Order, algorithm_context,
                             **kwargs) -> bool:
        pass

    def get_order_status(self, order: Order, algorithm_context,
                         **kwargs) -> OrderStatus:
        pass


class PortfolioManagerTestTwo(SQLLitePortfolioManager):
    trading_symbol = "USDT"
    market = "test"
    identifier = "testTwo"

    def get_unallocated_synced(self, algorithm_context):
        return 10000

    def get_positions_synced(self, algorithm_context):
        return [{"symbol": "SYMBOL_A", "amount": 2000}]


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.add_order_executor(OrderExecutorTestTwo)
        self.algo_app.add_portfolio_manager(PortfolioManagerTestTwo)
        self.start_algorithm()

    def tearDown(self) -> None:
        db.session.query(SQLLitePortfolio).delete()
        db.session.commit()
        super(Test, self).tearDown()

    def test(self) -> None:
        order = self.algo_app.algorithm\
            .create_limit_buy_order(
                self.TARGET_SYMBOL_A, self.BASE_SYMBOL_A_PRICE, 10
            )

        self.assert_is_limit_order(order)

    def test_with_execution(self) -> None:
        order = self.algo_app.algorithm\
            .create_limit_buy_order(
                self.TARGET_SYMBOL_A,
                self.BASE_SYMBOL_A_PRICE,
                10,
                execute=True
            )

        self.assert_is_limit_order(order)

        order.set_executed()

        self.assert_is_limit_order(order, True)

    def test_with_multiple_executors(self) -> None:
        order = self.algo_app.algorithm\
            .create_limit_buy_order(
                self.TARGET_SYMBOL_A,
                self.BASE_SYMBOL_A_PRICE,
                10,
                execute=True,
                identifier="testTwo",
                validate_pair=False
            )

        self.assert_is_limit_order(order)

        order.set_executed()

        self.assert_is_limit_order(order, True)