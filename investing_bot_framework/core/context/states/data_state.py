import time
from typing import List
from wrapt import synchronized

from investing_bot_framework.core.exceptions import ImproperlyConfigured, OperationalException
from investing_bot_framework.core.events import Observer
from investing_bot_framework.core.context.bot_context import BotContext
from investing_bot_framework.core.context.states import BotState
from investing_bot_framework.core.executors import ExecutionScheduler
from investing_bot_framework.core.data.data_providers import DataProvider, DataProviderExecutor
from investing_bot_framework.core.utils import Singleton, TimeUnit
from investing_bot_framework.core.configuration.config_constants import DEFAULT_MAX_WORKERS, SETTINGS_MAX_WORKERS, \
    SETTINGS_DATA_PROVIDER_REGISTERED_APPS


def import_class(cl):
    d = cl.rfind(".")
    classname = cl[d+1:len(cl)]
    m = __import__(cl[0:d], globals(), locals(), [classname])
    return getattr(m, classname)


class DataProviderScheduler(ExecutionScheduler, metaclass=Singleton):
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
            self.add_execution_task(execution_id=data_provider.get_id(), time_unit=TimeUnit.ALWAYS)

        self._configured = True

    @property
    def configured(self) -> bool:
        return self._configured


class DataState(BotState, Observer):
    """
    Represent the data state of a bot. This state will load all the defined data providers and will
    run them.

    If you want to validate the state before transitioning, provide a state validator.
    """

    from investing_bot_framework.core.context.states.strategy_state import StrategyState
    transition_state_class = StrategyState

    data_providers: List[DataProvider] = []
    _data_provider_executor: DataProviderExecutor

    def __init__(self, context: BotContext) -> None:
        super(DataState, self).__init__(context)

        self._updated = False
        self._configured = False
        self._initialize()

    def _initialize(self) -> None:
        """
        Initializes the data providers, loads them dynamically from the specified settings
        """
        self._clean_up()

        for data_provider_app_class in self.context.settings[SETTINGS_DATA_PROVIDER_REGISTERED_APPS]:

            instance = import_class(data_provider_app_class)()

            if not isinstance(instance, DataProvider):
                raise ImproperlyConfigured(
                    "Specified data provider {} is not a instance of DataProvider".format(data_provider_app_class)
                )

            self.data_providers.append(instance)

        self._configured = True

    def _clean_up(self) -> None:
        """
        Cleans up all the data state resources
        """

        self._data_provider_executor = None
        self.data_providers = []

    def _schedule_data_providers(self) -> List[DataProvider]:
        data_provider_scheduler = DataProviderScheduler()

        if not data_provider_scheduler.configured:
            data_provider_scheduler.configure(self.data_providers)

        planning = data_provider_scheduler.schedule_executions()
        planned_data_providers = []

        for data_provider in self.data_providers:

            if data_provider.get_id() in planning:
                planned_data_providers.append(data_provider)

        return planned_data_providers

    def _start_data_providers(self, data_providers: List[DataProvider]) -> None:

        self._data_provider_executor = DataProviderExecutor(
            data_providers=data_providers,
            max_workers=self.context.settings.get(SETTINGS_MAX_WORKERS, DEFAULT_MAX_WORKERS)
        )

        self._data_provider_executor.add_observer(self)
        self._data_provider_executor.start()

    def run(self) -> None:

        if self._configured:
            # Schedule the data providers
            planned_data_providers = self._schedule_data_providers()

            # Execute all the data providers
            self._start_data_providers(planned_data_providers)

            # Sleep till updated
            while not self._updated:
                time.sleep(1)

            # Collect all data from the data providers
            for data_provider in self._data_provider_executor.registered_data_providers:
                print("Data provider: {} finished running".format(data_provider.get_id()))

        else:
            raise OperationalException("Data state started without any configuration")

    def stop(self) -> None:
        """
        Stop all data providers
        """

        if self._configured:

            if self._data_provider_executor.processing:
                self._data_provider_executor.stop()

    def reconfigure(self) -> None:
        self._clean_up()
        self._initialize()

    @synchronized
    def update(self, observable, **kwargs) -> None:
        self._updated = True

