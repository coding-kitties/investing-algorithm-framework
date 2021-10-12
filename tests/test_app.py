from unittest import TestCase
from investing_algorithm_framework import App
from investing_algorithm_framework.configuration.constants import \
    RESOURCES_DIRECTORY


class Test(TestCase):

    def setUp(self) -> None:
        app = App()
        app._config = None

    def test_config_from_dict(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCES_DIRECTORY: "goaoge"}
        )
        app._initialize_config()
        self.assertIsNotNone(app.config.get("ENVIRONMENT"))
        self.assertIsNotNone(app.config.ENVIRONMENT)
        self.assertIsNotNone(app.config["ENVIRONMENT"])
