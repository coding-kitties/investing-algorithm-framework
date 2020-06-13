import time
import logging
from typing import List
from wrapt import synchronized

from investing_bot_framework.core.events import Observer
from investing_bot_framework.core.context.bot_context import BotContext
from investing_bot_framework.core.exceptions import OperationalException
from investing_bot_framework.core.context.states import BotState
from investing_bot_framework.core.executors import ExecutionScheduler
from investing_bot_framework.core.data_providers import DataProvider
from investing_bot_framework.core.executors.data_provider_executor import DataProviderExecutor
from investing_bot_framework.core.configuration.config_constants import DEFAULT_MAX_WORKERS, SETTINGS_MAX_WORKERS

logger = logging.getLogger(__name__)


class DataProviderScheduler(ExecutionScheduler):
    """
    Data Provider scheduler that will function as a scheduler to make sure it keeps it state across multiple states,
    it is defined as a Singleton.
    """

    def __init__(self):
        self._configured = False
        super(DataProviderScheduler, self).__init__()

    def configure(self, data_providers: List[DataProvider]) -> None:
        self._planning = {}

        for data_provider in data_providers:
            self.add_execution_task(
                execution_id=data_provider.get_id(),
                time_unit=data_provider.get_time_unit(),
                interval=data_provider.get_time_interval()
            )

        self._configured = True

    @property
    def configured(self) -> bool:
        return self._configured


class DataProviderState(BotState, Observer):
    """
    Represent the data_providers state of a bot. This state will load all the defined data_providers providers and will
    run them.

    If you want to validate the state before transitioning, provide a state validator.
    """

    registered_data_providers: List = None

    from investing_bot_framework.core.context.states.strategy_state import StrategyState
    transition_state_class = StrategyState

    data_provider_scheduler: DataProviderScheduler = None

    def __init__(self, context: BotContext) -> None:
        super(DataProviderState, self).__init__(context)
        self._updated = False
        self.data_provider_executor = None

    def _schedule_data_providers(self) -> List[DataProvider]:

        if not DataProviderState.data_provider_scheduler:
            DataProviderState.data_provider_scheduler = DataProviderScheduler()

        if not DataProviderState.data_provider_scheduler.configured:
            DataProviderState.data_provider_scheduler.configure(self.registered_data_providers)

        planning = DataProviderState.data_provider_scheduler.schedule_executions()
        planned_data_providers = []

        for data_provider in self.registered_data_providers:

            if data_provider.get_id() in planning:
                planned_data_providers.append(data_provider)

        return planned_data_providers

    def _start_data_providers(self, data_providers: List[DataProvider]) -> None:

        self.data_provider_executor = DataProviderExecutor(
            data_providers=data_providers,
            max_workers=self.context.settings.get(SETTINGS_MAX_WORKERS, DEFAULT_MAX_WORKERS)
        )

        if self.data_provider_executor.configured:
            self.data_provider_executor.add_observer(self)
            self.data_provider_executor.start()
        else:
            # Skip the execution
            self._updated = True

    def run(self) -> None:

        if self.registered_data_providers is None:
            raise OperationalException("Data providing state has not any data providers configured")

        # Schedule the data_providers providers
        planned_data_providers = self._schedule_data_providers()

        # Execute all the data_providers providers
        self._start_data_providers(planned_data_providers)

        # Sleep till updated
        while not self._updated:
            time.sleep(1)

        # Collect all data_providers from the data_providers providers
        for data_provider in self.data_provider_executor.registered_data_providers:
            logger.info("Data provider: {} finished running".format(data_provider.get_id()))

    def stop(self) -> None:
        """
        Stop all data_providers providers
        """
        pass

    @synchronized
    def update(self, observable, **kwargs) -> None:
        self._updated = True

    @staticmethod
    def register_data_providers(data_providers: List) -> None:
        DataProviderState.registered_data_providers = data_providers

    def reconfigure(self) -> None:
        pass



