from investing_algorithm_framework import OrderExecutor, OrderStatus, Order
from investing_algorithm_framework.core.exceptions import OperationalException
from tests.resources import TestBase


class MyOrderExecutorOne(OrderExecutor):
    identifier = "BINANCE"

    def execute_limit_order(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        pass

    def get_order_status(
            self, order: Order, algorithm_context, **kwargs
    ) -> OrderStatus:
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

    def test_retrieve(self):
        self.algo_app.algorithm.add_order_executor(MyOrderExecutorOne())

        order_executor = self.algo_app.algorithm.get_order_executor()
        self.assertIsNotNone(order_executor)

        order_executor = self.algo_app.algorithm.get_order_executor("BINANCE")
        self.assertIsNotNone(order_executor)
        self.assertEqual(order_executor.identifier, "BINANCE")
