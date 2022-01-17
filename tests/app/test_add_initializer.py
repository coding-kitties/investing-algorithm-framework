from unittest import TestCase
from investing_algorithm_framework import App, AlgorithmContextInitializer, \
    current_app, AlgorithmContext
from investing_algorithm_framework.configuration.constants import \
    RESOURCES_DIRECTORY


class InitializerTest(AlgorithmContextInitializer):

    def initialize(self, algorithm: AlgorithmContext) -> None:
        pass


class Test(TestCase):

    def tearDown(self) -> None:
        current_app.reset()

    def test_from_class(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCES_DIRECTORY: "goaoge"}
        )
        app.add_initializer(InitializerTest)
        self.assertIsNotNone(app.algorithm._initializer)

    def test_from_object(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCES_DIRECTORY: "goaoge"}
        )
        app.add_initializer(InitializerTest())
        self.assertIsNotNone(app.algorithm._initializer)
