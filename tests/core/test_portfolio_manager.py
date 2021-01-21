from unittest import TestCase

from investing_algorithm_framework.core.context import AlgorithmContext, \
    AlgorithmContextInitializer
from investing_algorithm_framework import DataProvider, \
    AbstractOrderExecutor, AbstractPortfolioManager, Strategy


class MyStrategy(Strategy):
    cycles = 0

    def on_raw_data(self, data_provider_id, data, algorithm_context):
        MyStrategy.cycles += 1
        algorithm_context.perform_limit_order('test_broker', 'btc', 10, 10, 10)


class MyDataProvider(DataProvider):
    cycles = 0
    registered_strategies = [MyStrategy()]

    def get_data(self, algorithm_context: AlgorithmContext):
        MyDataProvider.cycles += 1
        return 'data'


class MyOrderExecutor(AbstractOrderExecutor):
    execute_limit_order_called = False

    def __init__(self):
        super(MyOrderExecutor, self).__init__("test_broker")

    def execute_limit_order(
            self,
            asset: str,
            max_price: float,
            quantity: int,
            algorithm_context: AlgorithmContext, **kwargs
    ):
        MyOrderExecutor.execute_limit_order_called = True


class FullPortfolioManager(AbstractPortfolioManager):
    portfolio_size_called = False
    free_portfolio_size_called = False
    get_allocated_portfolio_size_called = False
    get_allocated_asset_size_called = False

    def __init__(self):
        super(FullPortfolioManager, self).__init__("test_broker")

    def get_portfolio_size(self, algorithm_context: AlgorithmContext):
        FullPortfolioManager.portfolio_size_called = True
        return 200

    def get_free_portfolio_size(self, algorithm_context: AlgorithmContext):
        FullPortfolioManager.free_portfolio_size_called = True
        return 0

    def get_allocated_portfolio_size(self, algorithm_context: AlgorithmContext):
        FullPortfolioManager.get_allocated_portfolio_size_called = True
        return 200

    def get_allocated_asset_size(
            self, asset, algorithm_context: AlgorithmContext
    ):
        FullPortfolioManager.get_allocated_asset_size_called = True
        return 200


class MyInitializer(AlgorithmContextInitializer):
    initializer_called = False

    def initialize(self, algorithm_context: AlgorithmContext) -> None:
        MyInitializer.initializer_called = True


class TestAlgorithmContext(TestCase):

    def test_running_with_full_portfolio_manager(self) -> None:
        context = AlgorithmContext(
            data_providers=[MyDataProvider()],
            order_executors=[MyOrderExecutor()],
            portfolio_managers=[FullPortfolioManager()],
            cycles=1,
            initializer=MyInitializer()
        )

        context.start()
        self.assertEqual(1, MyDataProvider.cycles)
        self.assertEqual(1, MyStrategy.cycles)
        self.assertFalse(FullPortfolioManager.portfolio_size_called)
        self.assertFalse(MyOrderExecutor.execute_limit_order_called)
        self.assertTrue(MyInitializer.initializer_called)
