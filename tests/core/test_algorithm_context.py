import pytest
from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.core.data_providers import DataProvider


class MyDataProvider(DataProvider):
    id = 'MyDataProvider'
    cycles = 0

    def get_data(self):
        MyDataProvider.cycles += 1
        return 'data'


def test_data_provider_registration() -> None:
    context = AlgorithmContext(MyDataProvider())

    assert context.data_provider is not None
    assert isinstance(context.data_provider, MyDataProvider)

    with pytest.raises(Exception) as exc_info:
        AlgorithmContext(MyDataProvider)

    assert str(exc_info.value) == 'Data provider must be an instance ' \
                                  'of the AbstractDataProvider class'


def test_running() -> None:
    context = AlgorithmContext(MyDataProvider(), cycles=1)
    context.start()
    assert MyDataProvider.cycles == 1

    context = AlgorithmContext(MyDataProvider(), cycles=2)
    context.start()
    assert MyDataProvider.cycles == 3
