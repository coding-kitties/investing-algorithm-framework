from enum import Enum

from bot import OperationalException
from bot.settings import BASE_DIR, PLUGIN_STRATEGIES_DIR, PLUGIN_DATA_PROVIDERS_DIR, TEST_CONFIGURATION_RESOURCES, \
    TEST_DATA_PROVIDER_RESOURCES, TEST_RESOURCES
"""
bot constants
"""

# Configuration
DEFAULT_CONFIG = 'config.json'
BASE_DIR = BASE_DIR

# Executor configuration
DEFAULT_MAX_WORKERS = 2

# Strategies
PLUGIN_STRATEGIES_DIR = PLUGIN_STRATEGIES_DIR

# Data providers
PLUGIN_DATA_PROVIDERS_DIR = PLUGIN_DATA_PROVIDERS_DIR

# Test resources
TEST_CONFIGURATION_RESOURCES = TEST_CONFIGURATION_RESOURCES
TEST_DATA_PROVIDER_RESOURCES = TEST_DATA_PROVIDER_RESOURCES
TEST_RESOURCES = TEST_RESOURCES


class TimeUnit(Enum):

    SECOND = 'SEC',
    MINUTE = 'MIN',
    HOUR = 'HR',
    ALWAYS = 'ALWAYS'

    # Static factory method to convert a string to time_unit
    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            if value.lower() in ('sec', 'second', 'seconds'):
                return TimeUnit.SECOND

            elif value.lower() in ('min', 'minute', 'minutes'):
                return TimeUnit.MINUTE

            elif value.lower() in ('hr', 'hour', 'hours'):
                return TimeUnit.HOUR

            elif value.lower() in ('always', 'every', 'continuous', 'every_time'):
                return TimeUnit.ALWAYS
            else:
                raise OperationalException('Could not convert value {} to a time_unit'.format(value))

        else:
            raise OperationalException("Could not convert non string value to a time_unit")

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:

            try:
                time_unit = TimeUnit.from_string(other)
                return time_unit == self
            except OperationalException:
                pass

            return other == self.value



