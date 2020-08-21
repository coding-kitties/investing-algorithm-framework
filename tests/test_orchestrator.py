import pytest
from investing_algorithm_framework.orchestrator import Orchestrator
from investing_algorithm_framework.core.data_providers import DataProvider


class MyDataProvider(DataProvider):
    id = 'my_data_provider'

    def get_data(self):
        return 'data'


class MyDataProviderTwo(DataProvider):
    id = 'my_data_provider_two'

    def get_data(self):
        return 'data'


def test_registration() -> None:
    data_provider = MyDataProvider()
    data_provider_two = MyDataProviderTwo()
    orchestrator = Orchestrator()
    orchestrator.register_data_provider(data_provider)
    orchestrator.register_data_provider(data_provider_two)

    assert orchestrator.registered_data_providers == [
        data_provider, data_provider_two
    ]

    with pytest.raises(AssertionError) as exc_info:
        orchestrator.register_data_provider(MyDataProviderTwo)

    assert str(exc_info.value) == 'Data provider must be an instance ' \
                                  'of the AbstractDataProvider class'
