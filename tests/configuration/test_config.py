from unittest import TestCase
from investing_algorithm_framework.configuration import Config
from tests.resources import random_string

TEST_VALUE = random_string(10)


class CustomConfig(Config):

    TEST_ATTRIBUTE = TEST_VALUE


class TestConfig(TestCase):
    ATTRIBUTE_ONE = "ATTRIBUTE_ONE"

    def test_config(self):
        config = Config()
        config.ATTRIBUTE_ONE = self.ATTRIBUTE_ONE
        self.assertIsNotNone(config.ATTRIBUTE_ONE)
        self.assertEqual(config.ATTRIBUTE_ONE, self.ATTRIBUTE_ONE)

    def test_from_class_instance(self):
        config = CustomConfig()
        self.assertIsNotNone(config.TEST_ATTRIBUTE)
        self.assertEqual(config.TEST_ATTRIBUTE, TEST_VALUE)

    def test_test_config_from_dict(self):
        config = Config.from_dict({self.ATTRIBUTE_ONE: self.ATTRIBUTE_ONE})
        self.assertIsNotNone(config.get(self.ATTRIBUTE_ONE))

    def test_get_item(self):
        config = CustomConfig()
        self.assertIsNotNone(config.get("TEST_ATTRIBUTE"))

    def test_set_item(self):
        config = CustomConfig()
        config.set(self.ATTRIBUTE_ONE, self.ATTRIBUTE_ONE)
        self.assertIsNotNone(config.get(self.ATTRIBUTE_ONE))
        self.assertIsNotNone(config.ATTRIBUTE_ONE)
