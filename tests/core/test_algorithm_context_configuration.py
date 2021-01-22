import pytest
from investing_algorithm_framework.core.context \
    import AlgorithmContextConfiguration
from investing_algorithm_framework.configuration.constants import BASE_DIR, \
    DATABASE_CONFIG, DATABASE_TYPE, DATABASE_NAME, \
    DATABASE_DIRECTORY_PATH
from tests.resources.utils import random_string


def test() -> None:
    config = AlgorithmContextConfiguration()
    config.load_settings_module('tests.resources.settings')

    assert config[BASE_DIR] is not None
    assert config[DATABASE_CONFIG] is not None

    database_config = config[DATABASE_CONFIG]

    assert database_config[DATABASE_TYPE] is not None
    assert database_config[DATABASE_NAME] is not None
    assert database_config[DATABASE_DIRECTORY_PATH] is not None

    new_attribute = random_string(10)
    new_attribute_value = random_string(10)

    config.set(new_attribute, new_attribute_value)

    assert config[new_attribute] is not None
    assert config[new_attribute] == new_attribute_value

    with pytest.raises(Exception):
        config.set(new_attribute, random_string(10))
