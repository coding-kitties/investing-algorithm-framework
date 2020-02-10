import time
from typing import List
from wrapt import synchronized

from bot.core.events import Observer
from bot.core.context.bot_context import BotContext
from bot.core.context.states import BotState
from bot.core.data.data_providers import DataProvider, DataProviderExecutor
from bot.core.resolvers import ClassCollector
from bot.core.exceptions import OperationalException
from bot.core.configuration.config_constants import DEFAULT_MAX_WORKERS, SETTINGS_DATA_PROVIDER_REGISTERED_APPS, \
    SETTINGS_MAX_WORKERS


class DataState(BotState, Observer):
    """
    Represent the data state of a bot. This state will load all the defined data providers and will
    run them.
    """

    from bot.core.context.states.strategy_state import StrategyState
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

        for data_provider_app_conf in self.context.settings[SETTINGS_DATA_PROVIDER_REGISTERED_APPS]:
            class_collector = ClassCollector(package_path=data_provider_app_conf, class_type=DataProvider)
            self.data_providers += class_collector.instances

        self._data_provider_executor = DataProviderExecutor(
            data_providers=self.data_providers,
            max_workers=self.context.settings.get(SETTINGS_MAX_WORKERS, DEFAULT_MAX_WORKERS)
        )

        # Adding self as an observer
        self._data_provider_executor.add_observer(self)
        self._configured = True

    def _clean_up(self) -> None:
        """
        Cleans up all the data state resources
        """

        self._data_provider_executor = None
        self.data_providers = []

    def run(self) -> None:

        if self._configured:
            # Start the data providers
            self._data_provider_executor.start()

            # Sleep till updated
            while not self._updated:
                time.sleep(1)

            # Collect all data from the data providers
            for data_provider in self._data_provider_executor.registered_data_providers:
                print(data_provider.get_id())

        else:
            raise OperationalException("Data state started without any configuration")

        print('stopped running')

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

