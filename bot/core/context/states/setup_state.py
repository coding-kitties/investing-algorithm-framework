import pkgutil
from importlib import import_module

from bot.core.configuration import settings
from bot.core.context.states import BotState
from bot.core.resolvers import ClassCollector
from bot.core.data_providers import DataProvider
from bot.core.configuration.config_constants import SETTINGS_DATA_PROVIDER_REGISTERED_APPS, SETTINGS_BOT_PROJECT_NAME


class SetupState(BotState):

    def __init__(self, context):
        super(SetupState, self).__init__(context)

    def run(self):
        # Initialize all data provider executors
        self._validate_data_providers()

        # from bot.context.data_providing_state import DataProvidingState
        # self.context.transition_to(DataProvidingState)
        # self.context.run()

    def _validate_data_providers(self) -> None:

        data_provider_apps_config = settings[SETTINGS_DATA_PROVIDER_REGISTERED_APPS]

        # Try to load all the specified modules
        for data_provider_app in data_provider_apps_config:
            # modules = [name for _, name, is_pkg in pkgutil.iter_modules([data_provider_app]) if not is_pkg and not name.startswith('_')]
            print(data_provider_app)
            module = import_module(data_provider_app)
            print(dir(module))
            class_collector = ClassCollector(data_provider_app, class_type=DataProvider)
            print(class_collector.instances)

    def stop(self):
        # Stopping all services
        pass

    def reconfigure(self):
        # Clean up and reconfigure all the services
        pass
