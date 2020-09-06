from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.orchestrator import Orchestrator
from investing_algorithm_framework.core.data_providers import DataProvider, \
    RelationalDataProvider
from tests.resources.utils import random_string


class MyDataProvider(DataProvider):
    id = 'my_data_provider'
    executed = False
    cycles = 0

    def __init__(self):
        super(MyDataProvider, self).__init__()
        MyDataProvider.executed = False
        MyDataProvider.cycles = 0

    def get_data(self, algorithm_context: AlgorithmContext):
        MyDataProvider.executed = True
        MyDataProvider.cycles += 1
        return 'data'


class MyDataProviderTwo(DataProvider):
    id = 'my_data_provider_two'
    executed = False
    cycles = 0

    def __init__(self):
        super(MyDataProviderTwo, self).__init__()
        MyDataProviderTwo.executed = False
        MyDataProviderTwo.cycles = 0

    def get_data(self, algorithm_context: AlgorithmContext):
        MyDataProviderTwo.executed = True
        MyDataProviderTwo.cycles += 1
        return 'data'


class MyDataProviderThree(RelationalDataProvider):
    id = 'my_data_provider_three'
    executed = False
    run_after = MyDataProviderTwo

    def __init__(self):
        super(MyDataProviderThree, self).__init__()
        MyDataProviderThree.executed = False
        MyDataProviderThree.cycles = 0

    def get_data(self, algorithm_context: AlgorithmContext):
        MyDataProviderThree.executed = True
        return 'data'


def test_running() -> None:
    data_provider = MyDataProvider()
    data_provider_two = MyDataProviderTwo()
    data_provider_three = MyDataProviderThree()

    algorithm_context = AlgorithmContext(random_string(10), data_provider)
    algorithm_context_two = AlgorithmContext(
        random_string(10), data_provider_two
    )
    algorithm_context_three = AlgorithmContext(
        random_string(10), data_provider_three
    )
    orchestrator = Orchestrator()
    orchestrator.register_algorithms([algorithm_context, algorithm_context_two])

    assert list(orchestrator.registered_algorithms.keys()) == [
        algorithm_context.get_id(),
        algorithm_context_two.get_id(),
    ]

    assert not MyDataProvider.executed
    assert not MyDataProviderTwo.executed
    assert MyDataProvider.cycles == 0
    assert MyDataProviderTwo.cycles == 0

    orchestrator.start_all_algorithms(cycles=1)

    assert MyDataProvider.executed
    assert MyDataProviderTwo.executed

    assert MyDataProvider.cycles == 1
    assert MyDataProviderTwo.cycles == 1

    # Relational data provider should not have run
    assert not MyDataProviderThree.executed

    orchestrator.register_algorithm(algorithm_context_three)

    assert list(orchestrator.registered_algorithms.keys()) == [
        algorithm_context.get_id(),
        algorithm_context_two.get_id(),
        algorithm_context_three.get_id()
    ]

    orchestrator.start_all_algorithms(cycles=1)
    assert MyDataProvider.cycles == 2
    assert MyDataProviderTwo.cycles == 2
    assert MyDataProviderThree.executed


def test_forced_idle() -> None:
    data_provider = MyDataProvider()
    algorithm_context = AlgorithmContext(random_string(10), data_provider)

    orchestrator = Orchestrator()
    orchestrator.register_algorithm(algorithm_context)
    orchestrator.start_all_algorithms(forced_idle=False)

    # Check if finished otherwise it will hang here
    assert True
