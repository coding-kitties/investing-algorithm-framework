from investing_algorithm_framework.configuration.settings import DevConfig
from investing_algorithm_framework.core.context import \
    AlgorithmContextConfiguration
from tests.resources import TestBase


class Test(TestBase):

    def setUp(self) -> None:
        super(Test, self).setUp()

    def test_config_add(self):
        self.algo_app._config = AlgorithmContextConfiguration()
        self.algo_app.initialize(config=DevConfig())
        self.algo_app.config.add("test", "value")
        self.assertIsNotNone(self.algo_app.config.get("test"))
        self.assertEqual(self.algo_app.config.get("test"), "value")
