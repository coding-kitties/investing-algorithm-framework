import logging
from pandas import DataFrame
from typing import Dict, Type, Any, List

from bot import OperationalException
from bot.data import DataProviderExecutor
from bot.context.bot_state import BotState
from bot.strategies import StrategyExecutor
from bot.utils import Singleton, DataSource


logger = logging.getLogger(__name__)


class BotContext(metaclass=Singleton):
    """
    The Context defines the interface of interest to clients. It also maintains
    a reference to an instance of a State subclass, which represents the current
    state of the Context.
    """

    """
    A reference to the current state of the Bot Context.
    """
    _state: BotState = None

    """
    List of all the buying and selling orders.
    """
    _buy_orders: DataFrame = None
    _sell_orders: DataFrame = None

    """
    The data sources for the bot
    """
    _analyzed_data: DataFrame = None
    _data_sources: List[DataSource] = None

    _strategy_executor = None
    _data_provider_executor: DataProviderExecutor = None

    def __init__(self) -> None:
        self._config = None

    def initialize(self, bot_state: Type[BotState]) -> None:

        if self._state:
            self._state.stop()

        self._state = bot_state()

    def transition_to(self, state: Type[BotState]) -> None:
        """
        The Context allows changing the State object at runtime.
        """

        logger.info("Bot context: Transition to {}".format(state.__name__))
        self._state = state()

    @property
    def config(self) -> Dict[str, Any]:

        if not self._config:
            raise OperationalException("Config is not specified in the context")

        return self._config

    @config.setter
    def config(self, config: Dict[str, Any]) -> None:
        self._config = config

    @property
    def analyzed_data(self) -> DataFrame:
        return self._analyzed_data

    @analyzed_data.setter
    def analyzed_data(self, data_frame: DataFrame) -> None:
        self._analyzed_data = data_frame

    @property
    def data_sources(self) -> List[DataSource]:
        return self._data_sources

    @data_sources.setter
    def data_sources(self, data_sources: List[DataSource]) -> None:
        self._data_sources = data_sources

    @property
    def data_provider_executor(self) -> DataProviderExecutor:

        if not self._data_provider_executor:
            raise OperationalException("Currently there is no data provider executor defined for the bot context")

        return self._data_provider_executor

    @data_provider_executor.setter
    def data_provider_executor(self, executor: DataProviderExecutor) -> None:
        self._data_provider_executor = executor

    @property
    def strategy_executor(self) -> StrategyExecutor:

        if not self._strategy_executor:
            raise OperationalException("Currently there is no strategy executor defined for the bot context")

        return self._strategy_executor

    @strategy_executor.setter
    def strategy_executor(self, executor: StrategyExecutor) -> None:
        self._strategy_executor = executor

    """
    The BotContext delegates part of its behavior to the current State object.
    """
    def run(self) -> None:

        if self._state:
            self._state.run()
        else:
            raise OperationalException("Bot context doesn't have a state")

    def stop(self) -> None:

        if self._state:
            self._state.stop()
        else:
            raise OperationalException("Bot context doesn't have a state")

    def reconfigure(self) -> None:

        if self._state:
            self._state.reconfigure()
        else:
            raise OperationalException("Bot context doesn't have a state")
