import logging

from bot.context.bot_state import BotState
from bot.constants import TimeUnit
from bot.configuration.resolvers import get_data_provider_configurations, load_data_provider

logger = logging.getLogger(__name__)


class SetupState(BotState):

    def __init__(self, context):
        logger.info("Initializing setup state ...")

        super(SetupState, self).__init__(context)

    def run(self):
        logger.info("Setup state started ...")

        # Initialize all data provider executors
        self._initialize_data_providers()

        logger.info("Setup state finished ...")

        from bot.context.data_providing_state import DataProvidingState
        self.context.transition_to(DataProvidingState)
        self.context.run()

    def _initialize_data_providers(self) -> None:
        """
        Function to load and initialize all the data providers.
        """

        logger.info("Initializing data providers ...")

        data_providers_config = get_data_provider_configurations(self.context.config)

        for data_provider_config in data_providers_config:
            schedule = data_provider_config.get('schedule')

            if isinstance(schedule, str):
                self.context.add_data_provider(
                    load_data_provider(data_provider_config),
                    TimeUnit.from_string(schedule),
                )
            else:
                self.context.add_data_provider(
                    load_data_provider(data_provider_config),
                    TimeUnit.from_string(schedule.get('time_unit')),
                    schedule.get('interval')
                )

    def stop(self):
        # Stopping all services
        pass

    def reconfigure(self):
        # Clean up and reconfigure all the services
        pass
