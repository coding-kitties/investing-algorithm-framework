from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.orchestrator import Orchestrator
from investing_algorithm_framework.core.data_providers import DataProvider
from tests.resources.utils import random_string


class MyDataProvider(DataProvider):
    id = 'my_data_provider'

    def get_data(self, algorithm_context: AlgorithmContext):
        return 'data'


class MyDataProviderTwo(DataProvider):
    id = 'my_data_provider_two'

    def get_data(self, algorithm_context: AlgorithmContext):
        return 'data'


def test_registration() -> None:
    data_provider = MyDataProvider()
    data_provider_two = MyDataProviderTwo()

    algorithm_context = AlgorithmContext(random_string(10), data_provider)
    algorithm_context_two = AlgorithmContext(
        random_string(10), data_provider_two
    )
    orchestrator = Orchestrator()
    orchestrator.register_algorithm(algorithm_context)
    orchestrator.register_algorithm(algorithm_context_two)

    assert orchestrator.registered_algorithms == [
        algorithm_context, algorithm_context_two
    ]
