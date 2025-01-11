import logging
from enum import Enum

from .exceptions import OperationalException

logger = logging.getLogger("investing_algorithm_framework")


class Environment(Enum):
    """
    Class TimeUnit: Enum for data_provider base type
    """
    DEV = 'DEV'
    PROD = 'PROD'
    TEST = 'TEST'
    BACKTEST = 'BACKTEST'

    # Static factory method to convert
    # a string to environment
    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in Environment:

                if value.upper() == entry.value:
                    return entry

            raise OperationalException(
                "Could not convert value to a environment type"
            )

        else:
            raise OperationalException(
                "Could not convert non string value to a environment type"
            )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:

            try:
                data_base_type = Environment.from_string(other)
                return data_base_type == self
            except OperationalException:
                pass

            return other == self.value


DEFAULT_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
        'file': {
            'class': 'logging.FileHandler',
            'formatter': 'default',
            'filename': 'app_logs.log',
        },
    },
    'loggers': {  # Make sure to add a 'loggers' section
        'investing_algorithm_framework': {  # Define your logger here
            'level': 'INFO',  # Set the desired level
            'handlers': ['console', 'file'],  # Use these handlers
            'propagate': False,
        },
    },
    'root': {  # Optional: Root logger configuration
        'level': 'WARNING',  # Root logger defaults to WARNING
        'handlers': ['console', 'file'],
    },
}
