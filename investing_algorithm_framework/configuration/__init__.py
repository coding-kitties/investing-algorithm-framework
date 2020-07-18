import os
import logging.config
from typing import Any
from importlib import import_module

from investing_algorithm_framework.core.exceptions \
    import ImproperlyConfigured, OperationalException
from investing_algorithm_framework.configuration.config_constants \
    import SETTINGS_MODULE_PATH_ENV_NAME,  SETTINGS_LOGGING_CONFIG


class ContextConfiguration:
    """
    Base wrapper for ContextConfiguration module. It will load all the
    default settings for a given settings module and will allow for run time
    specification
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

        # Set all the attributes of the settings wrapper
        for setting in dir(module):

            if setting.isupper():
                setting_value = getattr(module, setting)
                setattr(self, setting, setting_value)

        self._configured = True

        try:
            logging.config.dictConfig(self[SETTINGS_LOGGING_CONFIG])
        except Exception:
            # We ignore the error no logging configuration.
            pass

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
                    "ContextConfig object doesn't have the specific "
                    "attribute {}".format(item)
                )

            return self.__getattribute__(item)
        else:
            raise OperationalException(
                "ContextConfig attributes can only be referenced by string"
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

    def set(self, key: str, value: Any) -> None:

        if hasattr(self, key):
            raise OperationalException(
                "ContextConfig object already have the specific "
                "attribute {} specified".format(key)
            )

        setattr(self, key, value)
