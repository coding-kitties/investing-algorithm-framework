from tests.resources import TestBase
from investing_algorithm_framework import OrderExecutor, Order


class MyOrderExecutorOne(OrderExecutor):
    identifier = "MyOrderExecutorOne"

    def execute_order(
        self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        pass

    def check_order_status(
        self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        pass


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_order_executor(MyOrderExecutorOne())

    def test(self) -> None:
        order_executor = self.algo_app.algorithm \
            .get_order_executor(MyOrderExecutorOne.identifier)

        self.assertTrue(
            order_executor.identifier,
            MyOrderExecutorOne.identifier
        )
