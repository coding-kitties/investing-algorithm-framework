from investing_algorithm_framework.templates.data_providers import \
    DataProvider, RelationalDataProvider, ScheduledDataProvider
from investing_algorithm_framework.core.utils import TimeUnit
from investing_algorithm_framework.core.events import Observer


class TestObserver(Observer):
    update_count: int = 0

    def update(self, observable, **kwargs) -> None:
        self.update_count += 1


class TestDataProvider(DataProvider):
    id = 'TestDataProvider'

    def provide_data(self) -> None:
        pass


class TestScheduledDataProvider(ScheduledDataProvider):
    id = 'TestScheduledDataProvider'
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def provide_data(self) -> None:
        pass


class TestRelationalDataProvider(RelationalDataProvider):
    id = 'RelationalDataProvider'
    run_after = TestScheduledDataProvider

    def provide_data(self) -> None:
        pass


def test():
    data_provider_one = TestDataProvider()

    assert data_provider_one.id is not None
    assert data_provider_one.get_id() == TestDataProvider.id

    observer = TestObserver()
    data_provider_one.add_observer(observer)

    # Run the data provider
    data_provider_one.start()

    # Observer must have been updated
    assert observer.update_count == 1

    data_provider_two = TestScheduledDataProvider()

    assert data_provider_two.id is not None
    assert data_provider_two.get_id() == TestScheduledDataProvider.id

    data_provider_two.add_observer(observer)

    # Run the data provider
    data_provider_two.start()

    # Observer must have been updated
    assert observer.update_count == 2

    data_provider_three = TestRelationalDataProvider()

    assert data_provider_three.id is not None
    assert data_provider_three.get_id() == TestRelationalDataProvider.id

    data_provider_three.add_observer(observer)

    # Run the data provider
    data_provider_three.start()

    # Observer must have been updated
    assert observer.update_count == 3
