from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.core.data_providers import DataProvider


class MyDataProvider(DataProvider):
    id = 'my_data_provider'

    def get_data(self, algorithm_context: AlgorithmContext):
        return 'data'


class MyDataProviderTwo(DataProvider):
    id = 'my_data_provider_two'

    def get_data(self, algorithm_context: AlgorithmContext):
        return 'data'

