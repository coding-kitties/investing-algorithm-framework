from investing_bot_framework.core.exceptions import ImproperlyConfigured
from investing_bot_framework.core.context.states import BotState
from investing_bot_framework.core.resolvers import ClassCollector
from investing_bot_framework.core.data.data_providers import DataProvider
from investing_bot_framework.core.configuration.config_constants import SETTINGS_DATA_PROVIDER_REGISTERED_APPS


class SetupState(BotState):

    from investing_bot_framework.core.context.states.data_state import DataState
    transition_state_class = DataState

    def __init__(self, context):
        super(SetupState, self).__init__(context)
        
    def run(self) -> None:
        """
        Running the setup state.

        During execution a validation will be performed on:

        - DataProviders
        """

        # Load the settings
        if not self.context.settings.configured:
            raise ImproperlyConfigured(
                "Settings module is not specified, make sure you have setup a investing_bot_framework project and the investing_bot_framework is valid or that "
                "you have specified the settings module in your manage.py file"
            )

        # Initialize all data provider executors
        self._validate_data_providers()

    def _validate_data_providers(self) -> None:
        """
        Validates if all the data providers are correctly configured and can be loaded.
        """

        data_provider_apps_config = self.context.settings.get(SETTINGS_DATA_PROVIDER_REGISTERED_APPS, None)

        # Check if any data providers are configured
        if data_provider_apps_config is None or len(data_provider_apps_config) < 1:
            raise ImproperlyConfigured(
                "You have not configured any data provider apps in your settings file. Please define your data "
                "provider apps in your settings file. If you have difficulties configuring data providers, consider "
                "looking at the documentation."
            )

        # Try to load all the specified data provider modules
        for data_provider_app in data_provider_apps_config:
            class_collector = ClassCollector(package_path=data_provider_app, class_type=DataProvider)

            if len(class_collector.instances) == 0:
                raise ImproperlyConfigured(
                    "Could not load data providers from package {}, are they implemented correctly?. Please make sure "
                    "that you defined the right package or module. In the case of referring to your own defined data "
                    "providers make sure that they can be imported. If you have difficulties configuring data "
                    "providers, consider looking at the documentation.".format(data_provider_app)
                )

    def stop(self) -> None:
        # Stopping all services
        pass

    def reconfigure(self) -> None:
        # Clean up and reconfigure all the services
        pass

    def transition(self) -> None:

        # Transition to data state
        from investing_bot_framework.core.context.states.data_state import DataState
        self.context.transition_to(DataState)
        self.context.run()
