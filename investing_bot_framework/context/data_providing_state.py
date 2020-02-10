import time
import logging
from typing import List
from wrapt import synchronized

from investing_bot_framework.utils import DataSource
from investing_bot_framework import OperationalException
from investing_bot_framework.events.observer import Observer
from investing_bot_framework.context.bot_state import BotState
from investing_bot_framework.context.bot_context import BotContext
from investing_bot_framework.data import DataProvider, DataProviderExecutor

logger = logging.getLogger(__name__)


class DataProvidingState(BotState, Observer):

    def __init__(self, context: BotContext) -> None:
        super(DataProvidingState, self).__init__(context)

        logger.info("Initializing data providing state ...")

        self._data_provider_executor: DataProviderExecutor = None
        self.data_sources: List[DataSource] = []

        self._updated = False
        self._started = False

    def _initialize(self) -> None:
        data_providers = self.context.get_scheduled_data_providers()
        self._data_provider_executor = DataProviderExecutor(data_providers)
        self._data_provider_executor.add_observer(self)

    def _clean_up(self) -> None:
        self._updated = False
        self._started = False
        self._data_provider_executor = None
        self.data_sources = []

    def run(self) -> None:
        logger.info("Data providing state started ...")

        if not self._started:
            self._initialize()

        if len(self._data_provider_executor.registered_data_providers) > 0:
            self._data_provider_executor.start()

            # Sleep till updated
            while not self._updated:
                time.sleep(1)

            if self._updated:

                # Collect all data from the data providers
                for data_provider in self._data_provider_executor.registered_data_providers:
                    print(data_provider.get_id())
                    self.data_sources.append(DataSource(data_provider.get_id(), data_provider.data))
            else:
                raise OperationalException("Abruptly ended out of run state")

        # Transitioning to another state
        from investing_bot_framework.context.analyzing_state import AnalyzingState
        self.context.transition_to(AnalyzingState)
        self.context.run()

    def stop(self) -> None:
        if self._data_provider_executor is not None and self._data_provider_executor.processing:
            self._data_provider_executor.stop()

        self._clean_up()

    def reconfigure(self) -> None:
        self._clean_up()

    @synchronized
    def update(self, observable, **kwargs) -> None:
        self._updated = True
