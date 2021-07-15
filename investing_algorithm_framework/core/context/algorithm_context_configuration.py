from importlib import import_module
from typing import Any

from investing_algorithm_framework.core.exceptions \
    import ImproperlyConfigured, OperationalException


class AlgorithmContextConfiguration:
    """
    Base wrapper for ContextConfiguration module. It will load all the
    default settings for a given settings module and will allow for run time
    specification
    """

    def __init__(self) -> None:
        self.settings_module = None

    def load_settings_module(self, settings_module) -> None:
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
