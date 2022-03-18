from unittest import TestCase
from investing_algorithm_framework import App, DataProvider, current_app
from investing_algorithm_framework.configuration.constants import \
    RESOURCES_DIRECTORY


class DataProviderTest(DataProvider):
    market = "test"


class Test(TestCase):

    def tearDown(self) -> None:
        current_app.reset()

    def test_from_class(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCES_DIRECTORY: "goaoge"}
        )
        app.add_data_provider(DataProviderTest)
        self.assertEqual(1, len(app.algorithm._data_providers))
        data_provider = app.algorithm.get_data_provider("test")
        self.assertTrue(isinstance(data_provider, DataProvider))
        self.assertTrue(isinstance(data_provider, DataProviderTest))

    def test_from_object(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCES_DIRECTORY: "goaoge"}
        )
        app.add_data_provider(DataProviderTest())
        self.assertEqual(1, len(app.algorithm._data_providers))
        data_provider = app.algorithm.get_data_provider("test")
        self.assertTrue(isinstance(data_provider, DataProvider))
        self.assertTrue(isinstance(data_provider, DataProviderTest))
