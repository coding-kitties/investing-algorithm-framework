from typing import Dict, Any
from unittest import TestCase

from investing_bot_framework.core.data_providers import DataProvider
from investing_bot_framework.core.events import Observer


class TestDataProviderOne(DataProvider):

    id = 'TestDataProviderOne'

    def provide_data(self, **kwargs: Dict[str, Any]) -> Any:
        return "data_providers"


class TestDataProviderTwo(DataProvider):

    id = 'TestDataProviderTwo'

    def provide_data(self, **kwargs: Dict[str, Any]) -> Any:
        return "data_providers"


class TestObserver(Observer):

    def __init__(self) -> None:
        self.update_count = 0

    def update(self, observable, **kwargs) -> None:
        self.update_count += 1


class DataProviderSetup(TestCase):

    def test(self):
        data_provider_one = TestDataProviderOne()

        self.assertIsNotNone(data_provider_one.id)
        self.assertEqual(data_provider_one.get_id(), TestDataProviderOne.id)

        observer = TestObserver()
        data_provider_one.add_observer(observer)

        # Run the data_providers provider
        data_provider_one.start()

        # Observer must have been updated
        self.assertEqual(observer.update_count, 1)

        data_provider_two = TestDataProviderTwo()

        self.assertIsNotNone(data_provider_two.id)
        self.assertEqual(data_provider_two.get_id(), TestDataProviderTwo.id)

        data_provider_two.add_observer(observer)

        # Run the data_providers provider
        data_provider_two.start()

        # Observer must have been updated
        self.assertEqual(observer.update_count, 2)

        # Id´s must be different
        self.assertNotEqual(TestDataProviderOne.id, TestDataProviderTwo.id)