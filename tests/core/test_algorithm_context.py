import pytest

from investing_algorithm_framework.core.context import AlgorithmContext, \
    AlgorithmContextInitializer, AlgorithmContextConfiguration
from investing_algorithm_framework.core.data_providers import DataProvider
from tests.resources.utils import random_string


class MyDataProvider(DataProvider):
    id = 'MyDataProvider'
    cycles = 0

    def get_data(self, algorithm_context: AlgorithmContext):
        MyDataProvider.cycles += 1
        return 'data'


class MyInitializer(AlgorithmContextInitializer):

    def initialize(self, algorithm_context: AlgorithmContext) -> None:
        pass


def test_data_provider_registration() -> None:

    context = AlgorithmContext(MyDataProvider(), random_string(10))

    assert context.data_provider is not None
    assert isinstance(context.data_provider, MyDataProvider)

    with pytest.raises(Exception) as exc_info:
        AlgorithmContext(MyDataProvider, random_string(10))

    assert str(exc_info.value) == 'Data provider must be an instance ' \
                                  'of the AbstractDataProvider class'


def test_data_provider_id_creation() -> None:
    context = AlgorithmContext(MyDataProvider())
    assert context.algorithm_id is not None


def test_running() -> None:
    context = AlgorithmContext(MyDataProvider(), random_string(10), cycles=1)
    context.start()
    assert MyDataProvider.cycles == 1

    context = AlgorithmContext(MyDataProvider(), random_string(10), cycles=2)
    context.start()
    assert MyDataProvider.cycles == 3


def test_initializer_registration() -> None:
    initializer = MyInitializer()
    context = AlgorithmContext(
        MyDataProvider(), random_string(10), initializer
    )
    assert context.initializer is not None
    assert context.initializer is initializer

    context = AlgorithmContext(MyDataProvider(), random_string(10))
    context.set_algorithm_context_initializer(initializer)

    assert context.initializer is not None
    assert context.initializer is initializer

    # Check exceptions
    with pytest.raises(AssertionError) as exc_info:
        context = AlgorithmContext(MyDataProvider(), random_string(10))
        context.set_algorithm_context_initializer(MyInitializer)

    assert str(exc_info.value) == 'Initializer must be an instance of ' \
                                  'AlgorithmContextInitializer'


def test_config_registration() -> None:
    config = AlgorithmContextConfiguration()
    context = AlgorithmContext(
        MyDataProvider(), random_string(10),
        config=config
    )
    assert context.config is not None
    assert context.config == config
