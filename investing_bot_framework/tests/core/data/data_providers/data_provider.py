from investing_bot_framework.tests.core.data.data_providers.resources import TestDataProviderOne, \
    TestDataProviderTwo, TestObserver


def test():
    data_provider_one = TestDataProviderOne()

    assert data_provider_one.id is not None
    assert data_provider_one.get_id() == TestDataProviderOne.id

    observer = TestObserver()
    data_provider_one.add_observer(observer)

    # Run the data_providers provider
    data_provider_one.start()

    # Observer must have been updated
    assert observer.update_count == 1

    data_provider_two = TestDataProviderTwo()

    assert data_provider_two.id is not None
    assert data_provider_two.get_id() == TestDataProviderTwo.id

    data_provider_two.add_observer(observer)

    # Run the data_providers provider
    data_provider_two.start()

    # Observer must have been updated
    assert observer.update_count == 2

    # Id´s must be different
    assert TestDataProviderOne.id != TestDataProviderTwo.id
