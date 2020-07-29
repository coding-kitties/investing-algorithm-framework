from typing import Dict, Any

import pytest
from time import sleep
from investing_algorithm_framework.templates.states.data_providing_state \
    import DataProvidingState
from investing_algorithm_framework.templates.data_providers.data_provider \
    import DataProvider, ScheduledDataProvider, RelationalDataProvider
from investing_algorithm_framework.core.utils import TimeUnit
from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.workers import Worker


class TestObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        TestObserver.updated += 1


class CustomDataProvidingState(DataProvidingState):

    def get_transition_state_class(self):
        return None


class TestDataProviderOne(DataProvider):
    id = 'TestDataProviderOne'

    def provide_data(self) -> None:
        pass


class TestDataProviderTwo(ScheduledDataProvider):
    id = 'TestDataProviderTwo'
    time_interval = 1
    time_unit = TimeUnit.SECOND

    def provide_data(self) -> None:
        pass


class TestDataProviderThree(RelationalDataProvider):
    id = 'TestDataProviderThree'
    run_after = TestDataProviderTwo

    def provide_data(self) -> None:
        pass


class WrongDataProviderOne:

    def provide_data(self) -> None:
        pass


class WrongDataProviderTwo(Worker):

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass

    def provide_data(self) -> None:
        pass


def test() -> None:
    observer = TestObserver()
    data_provider_one = TestDataProviderOne()
    data_provider_one.add_observer(observer)
    data_provider_two = TestDataProviderTwo()
    data_provider_two.add_observer(observer)
    data_provider_three = TestDataProviderThree()
    data_provider_three.add_observer(observer)

    context = AlgorithmContext()
    CustomDataProvidingState.register_data_providers(
        [data_provider_one, data_provider_two]
    )
    data_providing_state = CustomDataProvidingState(context)
    data_providing_state.start()

    assert len(data_providing_state.registered_data_providers) == 2
    assert observer.updated == 2

    sleep(1)

    CustomDataProvidingState.register_data_providers(
        [data_provider_one, data_provider_two, data_provider_three]
    )
    data_providing_state.start()

    assert len(data_providing_state.registered_data_providers) == 3
    assert observer.updated == 5

    with pytest.raises(Exception):
        data_providing_state.register_data_providers([
            WrongDataProviderOne()
        ])

    with pytest.raises(Exception):
        data_providing_state.register_data_providers([
            WrongDataProviderTwo()
        ])
