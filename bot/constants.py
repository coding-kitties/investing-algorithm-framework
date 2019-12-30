from enum import Enum

"""
bot constants
"""
DEFAULT_CONFIG = 'config.json'
DEFAULT_MAX_WORKERS = 2


class TimeUnit(Enum):

    second = 'SEC',
    minute = 'MIN',
    hour = 'HR'

    # Static factory method to convert a string to TimeUnit
    @staticmethod
    def from_string(value: str):

        if value in ('SEC' 'sec', 'SECOND', 'second', 'SECONDS', 'seconds'):
            return TimeUnit.second

        elif value in ('MIN', 'min', 'MINUTE', 'minute', 'MINUTES', 'minutes'):
            return TimeUnit.minute

        elif value in ('HR', 'hr', 'HOUR', 'hour', 'HOURS', 'hour'):
            return
