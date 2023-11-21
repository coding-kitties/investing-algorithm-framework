from investing_algorithm_framework import create_app
from investing_algorithm_framework.domain import BACKTEST_DATA_DIRECTORY_NAME
from tests.resources import random_string, TestBase

TEST_VALUE = random_string(10)


class TestConfig(TestBase):
    ATTRIBUTE_ONE = "ATTRIBUTE_ONE"

    def test_config(self):
        app = create_app(
            config={self.ATTRIBUTE_ONE: self.ATTRIBUTE_ONE}
        )
        self.assertIsNotNone(app.config)

    def test_get_item(self):
        app = create_app(
            config={self.ATTRIBUTE_ONE: self.ATTRIBUTE_ONE}
        )
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app.config.get(self.ATTRIBUTE_ONE))
        self.assertIsNotNone(app.config.get(BACKTEST_DATA_DIRECTORY_NAME))

    def test_set_item(self):
        app = create_app(
            config={self.ATTRIBUTE_ONE: self.ATTRIBUTE_ONE}
        )
        self.assertIsNotNone(app.config)
        new_value = random_string(10)
        app.config.set(self.ATTRIBUTE_ONE, new_value)
        self.assertEqual(app.config.get(self.ATTRIBUTE_ONE), new_value)
