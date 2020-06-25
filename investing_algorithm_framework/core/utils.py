import sys
from threading import Thread
from wrapt import synchronized
from enum import Enum

from investing_algorithm_framework.core.exceptions import OperationalException


class Singleton(type):
    """
    Class Singleton: lets an instance that extends this class function as a
    Singleton. Only use this in a necessarily case.
    """

    _instances = {}

    @synchronized
    def __call__(cls, *args, **kwargs):

        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs
            )

        return cls._instances[cls]


class StoppableThread(Thread):
    """
    Class StoppableThread: Functions as a wrapper around a thread to add
    stop function
    """

    def __init__(self, *args, **keywords):
        Thread.__init__(self, *args, **keywords)
        self.killed = False

    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        if event == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True


class TimeUnit(Enum):
    """
    Class TimeUnit: Enum for TimeUnit
    """

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

            elif value.lower() in (
                    'always', 'every', 'continuous', 'every_time'
            ):
                return TimeUnit.ALWAYS
            else:
                raise OperationalException(
                    'Could not convert value {} to a time_unit'.format(value)
                )

        else:
            raise OperationalException(
                "Could not convert non string value to a time_unit"
            )

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
