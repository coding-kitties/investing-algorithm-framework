from bot.core.exceptions import ImproperlyConfigured
from bot.core.configuration import settings
from bot.core.context.states import BotState
from bot.core.resolvers import ClassCollector
from bot.core.data_providers import DataProvider
from bot.core.configuration.config_constants import SETTINGS_DATA_PROVIDER_REGISTERED_APPS


class SetupState(BotState):

    def __init__(self, context):
        super(SetupState, self).__init__(context)
        self.settings = None

    def run(self):
        self.settings = settings

        # Load the settings
        if not settings.configured:
            raise ImproperlyConfigured(
                "Settings module is not specified, make sure you have setup a bot project and the bot is valid or that "
                "you have specified the settings module in your manage.py file"
            )

        # Initialize all data provider executors
        self._validate_data_providers()

    def _validate_data_providers(self) -> None:

        data_provider_apps_config = self.settings[SETTINGS_DATA_PROVIDER_REGISTERED_APPS]

        # Try to load all the specified data provider modules
        for data_provider_app in data_provider_apps_config:
            class_collector = ClassCollector(data_provider_app, class_type=DataProvider)

            if len(class_collector.instances) == 0:
                raise ImproperlyConfigured(
                    "Could not load data providers from package {}, are they implemented correctly?. Please make sure "
                    "that you defined the right package or module. In the case of referring to your own defined data "
                    "providers make sure that they can be imported".format(data_provider_app)
                )

    def stop(self):
        # Stopping all services
        pass

    def reconfigure(self):
        # Clean up and reconfigure all the services
        pass
