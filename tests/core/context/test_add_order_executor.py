from investing_algorithm_framework import OrderExecutor, Order
from investing_algorithm_framework.core.exceptions import OperationalException
from tests.resources import TestBase


class MyOrderExecutorOne(OrderExecutor):
    identifier = "BINANCE"

    def execute_limit_order(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        pass

    def update_order_status(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        pass

    def execute_market_order(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        pass


class Test(TestBase):

    def test(self) -> None:
        self.algo_app.algorithm.add_order_executor(MyOrderExecutorOne())
        self.assertTrue(
            MyOrderExecutorOne.identifier in
            self.algo_app.algorithm._order_executors
        )

    def test_duplicate(self):
        self.algo_app.algorithm.add_order_executor(MyOrderExecutorOne())
        self.assertTrue(
            MyOrderExecutorOne.identifier in
            self.algo_app.algorithm._order_executors
        )
        with self.assertRaises(OperationalException):
            self.algo_app.algorithm.add_order_executor(MyOrderExecutorOne())
