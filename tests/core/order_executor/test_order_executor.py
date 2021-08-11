from tests.resources import TestBase
from investing_algorithm_framework import Order, OrderExecutor


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

    def setUp(self):
        self.order_executor = MyOrderExecutorOne()
        super(Test, self).setUp()

    def test_id(self):
        self.assertIsNotNone(self.order_executor.identifier)
        self.assertIsNotNone(self.order_executor.get_id())
        self.order_executor.identifier = None

        with self.assertRaises(AssertionError):
            self.order_executor.get_id()

    def test_initialize(self):
        self.order_executor.initialize(self.algo_app.algorithm)
