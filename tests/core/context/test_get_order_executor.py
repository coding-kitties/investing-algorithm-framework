from tests.resources import TestBase
from investing_algorithm_framework import OrderExecutor, Order


class MyOrderExecutorOne(OrderExecutor):
    identifier = "MyOrderExecutorOne"

    def execute_limit_order(self, order: Order, algorithm_context,
                            **kwargs) -> bool:
        pass

    def get_order_status(self, order: Order, algorithm_context,
                            **kwargs) -> bool:
        pass

    def execute_market_order(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        pass


class MyOrderExecutorTwo(OrderExecutor):
    identifier = "MyOrderExecutorTwo"

    def execute_limit_order(self, order: Order, algorithm_context,
                            **kwargs) -> bool:
        pass

    def get_order_status(self, order: Order, algorithm_context,
                            **kwargs) -> bool:
        pass

    def execute_market_order(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        pass


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_order_executor(MyOrderExecutorOne())
        self.algo_app.algorithm.add_order_executor(MyOrderExecutorTwo())

    def test(self) -> None:
        order_executor = self.algo_app.algorithm \
            .get_order_executor(MyOrderExecutorOne.identifier)

        self.assertTrue(
            order_executor.identifier,
            MyOrderExecutorOne.identifier
        )

        order_executor = self.algo_app.algorithm \
            .get_order_executor(MyOrderExecutorTwo.identifier)

        self.assertTrue(
            order_executor.identifier,
            MyOrderExecutorTwo.identifier
        )
