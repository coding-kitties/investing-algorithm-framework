import os
from tests.utils import random_string
from bot.constants import PLUGIN_DATA_PROVIDERS_DIR
from bot.constants import TEST_CONFIGURATION_RESOURCES

TEST_DATA_PROVIDERS_PLUGINS_FILE = os.path.join(
    PLUGIN_DATA_PROVIDERS_DIR, '{}_data_provider.py'.format(random_string(10))
)

TEST_SAMPLE_CONFIG_ONE = os.path.join(TEST_CONFIGURATION_RESOURCES, 'sample_configuration_one.json')
