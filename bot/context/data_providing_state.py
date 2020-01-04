import logging
from time import sleep
from typing import List
from wrapt import synchronized

from bot.utils import DataSource
from bot import OperationalException
from bot.events.observer import Observer
from bot.context.bot_state import BotState
from bot.context.bot_context import BotContext
from bot.data.data_provider_executor import DataProviderExecutor

logger = logging.getLogger(__name__)


class DataProvidingState(BotState, Observer):

    def __init__(self) -> None:
        super(DataProvidingState, self).__init__()

        logger.info("Initializing data providing state ...")

        # Initialize the manager
        context = BotContext()

        self._data_provider_executor: DataProviderExecutor = context.data_provider_executor
        self._data_provider_executor.add_observer(self)

        self._updated = False
        self._started = False

    def _clean_up(self) -> None:

        if self._data_provider_executor.processing:
            self._data_provider_executor.stop()

        self._updated = False
        self._started = False

    def run(self) -> None:
        logger.info("Data providing state started ...")

        data_sources: List[DataSource] = []

        if not self._started:
            self._data_provider_executor.start()

        # Sleep till updated
        while not self._updated:
            sleep(1)

        if self._updated:

            # Collect all data from the data providers
            for data_provider in self._data_provider_executor.registered_data_providers:
                data_sources.append(DataSource(data_provider.get_id(), data_provider.data))

            context = BotContext()
            context.data_sources = data_sources

            # Transitioning to another state
            from bot.context.analyzing_state import AnalyzingState
            context.transition_to(AnalyzingState)
            context.run()
        else:
            raise OperationalException("Abruptly ended out of run state")

    def stop(self) -> None:
        pass

    def reconfigure(self) -> None:
        self._clean_up()

    @synchronized
    def update(self, observable, **kwargs) -> None:
        self._updated = True
