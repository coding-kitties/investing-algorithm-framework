from unittest import TestCase
from investing_algorithm_framework import App
from investing_algorithm_framework.configuration.constants import \
    RESOURCE_DIRECTORY


class Test(TestCase):

    def setUp(self) -> None:
        app = App()
        app._config = None

    def test_config_from_dict(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCE_DIRECTORY: "goaoge"}
        )
        self.assertIsNotNone(app.config.get("ENVIRONMENT"))
