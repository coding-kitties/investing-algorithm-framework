import os
import logging.config
from typing import Any
from importlib import import_module
from enum import Enum

from investing_algorithm_framework.core.exceptions \
    import ImproperlyConfigured, OperationalException
from investing_algorithm_framework.configuration.config_constants \
    import SETTINGS_MODULE_PATH_ENV_NAME, \
    SETTINGS_STRATEGY_REGISTERED_APPS, SETTINGS_LOGGING_CONFIG, \
    SETTINGS_DATA_PROVIDER_REGISTERED_APPS


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


class BaseSettings:
    """
    Base wrapper for settings module. It will load all the default settings
    for a given settings module
    """

    def __init__(self) -> None:
        self._configured = False
        self._settings_module = None

    def configure(self, settings_module: str = None) -> None:
        self._settings_module = settings_module

        if settings_module is None:
            self.settings_module = os.environ.get(
                SETTINGS_MODULE_PATH_ENV_NAME
            )
        else:
            self.settings_module = settings_module

        if self.settings_module is None:
            raise ImproperlyConfigured("There is no settings module defined")

        # Load the settings module
        module = import_module(self.settings_module)

        # Base components
        tuple_settings = (
            SETTINGS_STRATEGY_REGISTERED_APPS,
            SETTINGS_DATA_PROVIDER_REGISTERED_APPS,
        )

        # Set all the attributes of the settings wrapper
        for setting in dir(module):

            if setting.isupper():
                setting_value = getattr(module, setting)

                if setting in tuple_settings and \
                        not isinstance(setting_value, (list, tuple)):
                    raise ImproperlyConfigured(
                        "The {} setting must be a list or a "
                        "tuple.".format(setting))

                setattr(self, setting, setting_value)

        self._configured = True

        logging.config.dictConfig(self[SETTINGS_LOGGING_CONFIG])

    @property
    def settings_module(self) -> str:
        return self._settings_module

    @settings_module.setter
    def settings_module(self, settings_module: str) -> None:
        self._settings_module = settings_module

    @property
    def configured(self) -> bool:
        return self._configured

    def __getitem__(self, item) -> Any:

        if isinstance(item, str):

            if not hasattr(self, item):
                raise OperationalException(
                    "Setting object doesn't have the specific "
                    "attribute {}".format(item)
                )

            return self.__getattribute__(item)
        else:
            raise OperationalException(
                "Settings attributes can only be referenced by string"
            )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Mimics the dict get() functionality
        """

        try:
            return self.__getitem__(key)
        # Ignore exception
        except OperationalException:
            pass

        return default


settings = BaseSettings()
