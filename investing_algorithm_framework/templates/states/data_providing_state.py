import time
import logging
from typing import List
from wrapt import synchronized

from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.context.context import Context
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.state import State
from investing_algorithm_framework.core.executors import ExecutionScheduler
from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.templates.data_providers import DataProvider
from investing_algorithm_framework.core.executors import Executor
from investing_algorithm_framework.configuration.config_constants \
    import DEFAULT_MAX_WORKERS, SETTINGS_MAX_WORKERS

logger = logging.getLogger(__name__)


class DataProviderExecutor(Executor):
    """
    Class DataProviderExecutor: is an executor for DataProvider instances.
    """

    def __init__(
            self,
            data_providers: List[DataProvider] = None,
            max_workers: int = DEFAULT_MAX_WORKERS
    ):
        super(DataProviderExecutor, self).__init__(max_workers=max_workers)

        self._registered_data_providers: List[DataProvider] = []

        if data_providers is not None and len(data_providers) > 0:
            self._registered_data_providers = data_providers

    def create_workers(self) -> List[Worker]:
        return self._registered_data_providers

    @property
    def registered_data_providers(self) -> List[DataProvider]:
        return self._registered_data_providers

    @property
    def configured(self):
        return self._registered_data_providers is not None \
               and len(self._registered_data_providers) > 0


class DataProviderScheduler(ExecutionScheduler):
    """
    Data Provider scheduler that will function as a scheduler to make sure it
    keeps it state across multiple state, it is defined as a Singleton.
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


class DataProvidingState(State, Observer):
    """
    Represent the data_providers state of a bot. This state will load all \
    the defined data_providers providers and will run them.

    If you want to validate the state before transitioning, provide a
    state validator.
    """

    registered_data_providers: List = None

    from investing_algorithm_framework.templates.states.strategy_state \
        import StrategyState
    transition_state_class = StrategyState

    data_provider_scheduler: DataProviderScheduler = None

    def __init__(self, context: Context) -> None:
        super(DataProvidingState, self).__init__(context)
        self._updated = False
        self.data_provider_executor = None

        if self.registered_data_providers is None \
                or len(self.registered_data_providers) < 1:
            raise OperationalException(
                "Data providing state has not any data providers configured"
            )

    def _schedule_data_providers(self) -> List[DataProvider]:

        if not DataProvidingState.data_provider_scheduler:
            DataProvidingState.data_provider_scheduler = \
                DataProviderScheduler()

        if not DataProvidingState.data_provider_scheduler.configured:
            DataProvidingState.data_provider_scheduler.configure(
                self.registered_data_providers
            )

        planning = DataProvidingState.data_provider_scheduler.\
            schedule_executions()
        planned_data_providers = []

        for data_provider in self.registered_data_providers:

            if data_provider.get_id() in planning:
                planned_data_providers.append(data_provider)

        return planned_data_providers

    def _start_data_providers(self, data_providers: List[DataProvider]) \
            -> None:

        self.data_provider_executor = DataProviderExecutor(
            data_providers=data_providers,
            max_workers=self.context.settings.get(
                SETTINGS_MAX_WORKERS, DEFAULT_MAX_WORKERS
            )
        )

        if self.data_provider_executor.configured:
            self.data_provider_executor.add_observer(self)
            self.data_provider_executor.start()
        else:
            # Skip the execution
            self._updated = True

    def run(self) -> None:

        # Schedule the data_providers providers
        planned_data_providers = self._schedule_data_providers()

        # Execute all the data_providers providers
        self._start_data_providers(planned_data_providers)

        # Sleep till updated
        while not self._updated:
            time.sleep(1)

        # Collect all data_providers from the data_providers providers
        for data_provider in self.data_provider_executor\
                .registered_data_providers:
            logger.info("Data provider: {} finished running".format(
                data_provider.get_id())
            )

    @synchronized
    def update(self, observable, **kwargs) -> None:
        self._updated = True

    @staticmethod
    def register_data_providers(data_providers: List) -> None:
        DataProvidingState.registered_data_providers = data_providers
