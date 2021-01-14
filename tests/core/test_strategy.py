from unittest import TestCase

from investing_algorithm_framework.core.strategies import Strategy
from investing_algorithm_framework.core.data_providers import DataProvider
from investing_algorithm_framework.core.context import AlgorithmContext


class MyStrategy(Strategy):
    id = 'my_strategy'


class MyStrategyTwo(Strategy):

    def on_tick(self, data, algorithm_context: AlgorithmContext):
        raise Exception()


class MyStrategyThree(Strategy):

    def get_id(self) -> str:
        return 'my_strategy_three'


class MyDataProvider(DataProvider):
    registered_strategies = [MyStrategy()]

    def extract_tick(self, data, algorithm_context: AlgorithmContext):
        return data

    def get_data(self, algorithm_context: AlgorithmContext):
        return 'tick'


class TestStrategy(TestCase):

    def test_id(self) -> None:
        strategy = MyStrategy()

        self.assertEqual('my_strategy', strategy.get_id())
