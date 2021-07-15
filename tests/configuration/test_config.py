from unittest import TestCase
from investing_algorithm_framework.configuration import Config


class TestConfig(TestCase):
    ATTRIBUTE_ONE = "ATTRIBUTE_ONE"

    def test_config(self):
        config = Config()
        config.ATTRIBUTE_ONE = self.ATTRIBUTE_ONE
        self.assertIsNotNone(config.ATTRIBUTE_ONE)
        self.assertEqual(config.ATTRIBUTE_ONE, self.ATTRIBUTE_ONE)

