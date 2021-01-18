from unittest import TestCase
from investing_algorithm_framework.core.context \
    import AlgorithmContextConfiguration
from investing_algorithm_framework.configuration.constants import BASE_DIR, \
    DATABASE_CONFIG, DATABASE_TYPE, DATABASE_NAME, \
    DATABASE_DIRECTORY_PATH
from tests.resources.utils import random_string


class TestAlgorithmContextConfiguration(TestCase):

    def test(self) -> None:
        config = AlgorithmContextConfiguration()
        config.load_settings_module('tests.resources.settings')

        self.assertIsNotNone(config[BASE_DIR])
        self.assertIsNotNone(config[DATABASE_CONFIG])

        database_config = config[DATABASE_CONFIG]

        self.assertIsNotNone(database_config[DATABASE_TYPE])
        self.assertIsNotNone(database_config[DATABASE_NAME])
        self.assertIsNotNone(database_config[DATABASE_DIRECTORY_PATH])

        new_attribute = random_string(10)
        new_attribute_value = random_string(10)

        config.set(new_attribute, new_attribute_value)

        self.assertIsNotNone(config[new_attribute])
        self.assertEqual(config[new_attribute], new_attribute_value)

        with self.assertRaises(Exception):
            config.set(new_attribute, random_string(10))
