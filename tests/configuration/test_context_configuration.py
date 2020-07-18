import pytest
from investing_algorithm_framework.configuration import ContextConfiguration
from investing_algorithm_framework.configuration.config_constants import \
    SETTINGS_CONTEXT_CONFIGURATION, SETTINGS_LOGGING_CONFIG, \
    SETTINGS_MAX_CONCURRENT_WORKERS, SETTINGS_PROJECT_NAME, BASE_DIR
from tests.resources.utils import random_string


def test() -> None:
    config = ContextConfiguration()
    config.configure('tests.resources.standard_settings')
    assert config.configured

    assert config[BASE_DIR] is not None
    assert config[SETTINGS_CONTEXT_CONFIGURATION] is not None
    assert config[SETTINGS_LOGGING_CONFIG] is not None
    assert config[SETTINGS_MAX_CONCURRENT_WORKERS] is not None
    assert config[SETTINGS_PROJECT_NAME] is not None

    new_attribute = random_string(10)
    new_attribute_value = random_string(10)

    config.set(new_attribute, new_attribute_value)

    assert config[new_attribute] is not None
    assert config[new_attribute] == new_attribute_value

    with pytest.raises(Exception):
        config.set(new_attribute, random_string(10))
