from importlib import import_module

from bot.core.exceptions import ImproperlyConfigured


class Settings:
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
            'INSTALLED_DATA_PROVIDERS',
            'INSTALLED_STRATEGIES',
            'INSTALLED_MARKET_MAKERS'
        )

        # Set all the attributes of the settings wrapper
        for setting in dir(module):
            if setting.isupper():
                setting_value = getattr(module, setting)

                if (setting in tuple_settings and
                        not isinstance(setting_value, (list, tuple))):
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
