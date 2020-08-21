from investing_algorithm_framework.core.strategies import Strategy
from investing_algorithm_framework.core.data_providers import DataProvider


class MyStrategy(Strategy):
    id = 'my_strategy'


class MyStrategyTwo(Strategy):
    id = 'my_strategy_two'


class MyStrategyThree(Strategy):

    def get_id(self) -> str:
        return 'my_strategy_three'


class MyDataProvider(DataProvider):
    registered_strategies = [MyStrategy()]

    def extract_tick(self, data):
        return data

    def get_data(self):
        return 'tick'


def test_id() -> None:

    strategy = MyStrategy()
    strategy_two = MyStrategyTwo()
    strategy_three = MyStrategyThree()

    assert strategy.get_id() == 'my_strategy'
    assert strategy_two.get_id() == 'my_strategy_two'
    assert strategy_three.get_id() == 'my_strategy_three'


def test_not_implemented() -> None:
    data_provider = MyDataProvider()
    data_provider.provide_data()

