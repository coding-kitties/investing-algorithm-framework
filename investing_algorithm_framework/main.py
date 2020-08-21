from investing_algorithm_framework.core.strategies import Strategy
from investing_algorithm_framework.core.data_providers import DataProvider
from investing_algorithm_framework.orchestrator import Orchestrator


class MyStrategy(Strategy):

    def on_tick(self, data):
        pass


class MyDataProvider(DataProvider):
    id = 'MyDataProvider'
    registered_strategies = [MyStrategy()]

    def extract_tick(self, data):
        return data

    def get_data(self):
        return 'data'


if __name__ == '__main__':
    orchestrator = Orchestrator()
    orchestrator.register_data_provider(MyDataProvider())
    orchestrator.start()
