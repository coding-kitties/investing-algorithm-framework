import os
from typing import Any
from importlib import import_module

from bot.core.exceptions import ImproperlyConfigured, OperationalException
from bot.core.configuration.template import Template
from bot.core.configuration.config_constants import SETTINGS_MODULE_PATH_ENV_NAME, SETTINGS_STRATEGY_REGISTERED_APPS, \
    SETTINGS_DATA_PROVIDER_REGISTERED_APPS


class BaseSettings:
    """
    Base wrapper for settings module. It will load all the default settings for a given settings module
    """

    def __init__(self, settings_module: str = None) -> None:
        self._configured = False
        self._settings_module = settings_module

        if self._settings_module is not None:
            self.configure()

    def configure(self) -> None:

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

                if setting in tuple_settings and not isinstance(setting_value, (list, tuple)):
                    raise ImproperlyConfigured("The %s setting must be a list or a tuple. " % setting)

                setattr(self, setting, setting_value)

        self._configured = True

    @property
    def settings_module(self) -> str:
        return self._settings_module

    @settings_module.setter
    def settings_module(self, settings_module: str) -> None:
        self._settings_module = settings_module
        self.configure()

    @property
    def configured(self) -> bool:
        return self._configured

    def __getitem__(self, item) -> Any:

        print(item)

        if isinstance(item, str):

            if not hasattr(self, item):
                raise OperationalException("Setting object doesn't have the specific attribute {}".format(item))

            return self.__getattribute__(item)
        else:
            raise OperationalException("Settings attributes can only be referenced by string")


def resolve_settings():
    return BaseSettings(os.environ.get(SETTINGS_MODULE_PATH_ENV_NAME))


settings = resolve_settings()
