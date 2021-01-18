from unittest import TestCase

from investing_algorithm_framework.core.strategies import Strategy
from investing_algorithm_framework.core.data_providers import DataProvider
from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework import AbstractPortfolioManager, \
    AbstractOrderExecutor


class MyOrderExecutor(AbstractOrderExecutor):
    execute_limit_order_called = True

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


class MyPortfolioManager(AbstractPortfolioManager):
    portfolio_size_called = False
    free_portfolio_size_called = False
    get_allocated_portfolio_size_called = False
    get_allocated_asset_size_called = False

    def __init__(self):
        super(MyPortfolioManager, self).__init__("test_broker")

    def get_portfolio_size(self, algorithm_context: AlgorithmContext):
        MyPortfolioManager.portfolio_size_called = True
        return 200

    def get_free_portfolio_size(self, algorithm_context: AlgorithmContext):
        MyPortfolioManager.free_portfolio_size_called = True
        return 200

    def get_allocated_portfolio_size(self, algorithm_context: AlgorithmContext):
        MyPortfolioManager.get_allocated_portfolio_size_called = True
        return 0

    def get_allocated_asset_size(
            self, asset, algorithm_context: AlgorithmContext
    ):
        MyPortfolioManager.get_allocated_asset_size_called = True
        return 0


class MyStrategy(Strategy):
    id = 'my_strategy'


class MyStrategyTwo(Strategy):
    data_provider_id = None

    def on_tick(
            self, data_provider_id, data, algorithm_context: AlgorithmContext
    ):
        MyStrategyTwo.data_provider_id = data_provider_id


class MyStrategyThree(Strategy):
    data_provider_id = None

    def get_id(self) -> str:
        return 'my_strategy_three'

    def on_raw_data(self, data_provider_id, data, algorithm_context):
        MyStrategyThree.data_provider_id = data_provider_id


class MyDataProvider(DataProvider):
    registered_strategies = [MyStrategy(), MyStrategyTwo(), MyStrategyThree()]

    def extract_tick(self, data, algorithm_context: AlgorithmContext):
        return data

    def get_data(self, algorithm_context: AlgorithmContext):
        return 'tick'


class TestStrategy(TestCase):

    def test_id(self) -> None:
        strategy = MyStrategy()

        self.assertEqual('my_strategy', strategy.get_id())

    def test_run(self):
        data_provider = MyDataProvider()
        context = AlgorithmContext(
            data_providers=[data_provider],
            order_executors=[MyOrderExecutor()],
            portfolio_managers=[MyPortfolioManager()],
            cycles=1
        )

        context.start()
        self.assertEqual(
            MyStrategyTwo.data_provider_id, data_provider.get_id()
        )
        self.assertEqual(
            MyStrategyThree.data_provider_id, data_provider.get_id()
        )
