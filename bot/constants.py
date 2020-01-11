from enum import Enum

from bot import OperationalException
from bot.settings import BASE_DIR, PLUGIN_STRATEGIES_DIR, PLUGIN_DATA_PROVIDERS_DIR
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


class TimeUnit(Enum):

    SECOND = 'SEC',
    MINUTE = 'MIN',
    HOUR = 'HR',
    ALWAYS = 'ALWAYS'

    # Static factory method to convert a string to time_unit
    @staticmethod
    def from_string(value: str):

        if value in ('SEC' 'sec', 'SECOND', 'second', 'SECONDS', 'seconds'):
            return TimeUnit.SECOND

        elif value in ('MIN', 'min', 'MINUTE', 'minute', 'MINUTES', 'minutes'):
            return TimeUnit.MINUTE

        elif value in ('HR', 'hr', 'HOUR', 'hour', 'HOURS', 'hour'):
            return TimeUnit.HOUR
        else:
            raise OperationalException('Could not convert value {} to a time_unit'.format(value))

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


class ExecutionMode(Enum):

    SYNCHRONOUS = 'synchronous',
    ASYNCHRONOUS = 'asynchronous'

    @staticmethod
    def from_string(value: str):

        if value in ('async', 'asynchronous'):
            return ExecutionMode.ASYNCHRONOUS

        elif value in ('sync', 'synchronous', 'synchronized'):
            return ExecutionMode.SYNCHRONOUS
        else:
            raise OperationalException('Could not convert value {} to a ExecutionMode'.format(value))

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            try:
                execution_mode = ExecutionMode.from_string(other)
                return execution_mode == self
            except OperationalException:
                pass

            return other == self.value



