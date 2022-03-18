from investing_algorithm_framework import OrderExecutor, Order
from tests.resources import TestBase


class OrderExecutorTest(OrderExecutor):
    identifier = "test"

    def execute_order(self, order: Order, algorithm_context,
                      **kwargs) -> Order:
        pass

    def check_order_status(self, order: Order, algorithm_context,
                           **kwargs) -> Order:
        pass


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_order_executor(OrderExecutorTest())

    def test_retrieve(self):
        order_executor = self.algo_app.algorithm.get_order_executor("test")
        self.assertIsNotNone(order_executor)
        self.assertEqual(order_executor.identifier, "test")
