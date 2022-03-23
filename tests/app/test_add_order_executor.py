from unittest import TestCase

from investing_algorithm_framework import App, OrderExecutor, Order, \
    current_app
from investing_algorithm_framework.configuration.constants import \
    RESOURCE_DIRECTORY


class OrderExecutorTest(OrderExecutor):

    def execute_order(
        self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        pass

    def check_order_status(
        self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        pass

    identifier = "test"


class Test(TestCase):

    def tearDown(self) -> None:
        current_app.reset()

    def test_from_class(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCE_DIRECTORY: "goaoge"}
        )
        app.add_order_executor(OrderExecutorTest)
        self.assertEqual(1, len(app.algorithm._order_executors))
        order_executor = app.algorithm.get_order_executor("test")
        self.assertTrue(isinstance(order_executor, OrderExecutorTest))
        self.assertTrue(isinstance(order_executor, OrderExecutorTest))

    def test_from_object(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCE_DIRECTORY: "goaoge"}
        )
        app.add_order_executor(OrderExecutorTest())
        self.assertEqual(1, len(app.algorithm._order_executors))
        order_executor = app.algorithm.get_order_executor("test")
        self.assertTrue(isinstance(order_executor, OrderExecutorTest))
        self.assertTrue(isinstance(order_executor, OrderExecutorTest))
