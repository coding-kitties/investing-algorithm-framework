import logging
from typing import Dict, Type, Any
from pandas import DataFrame

from bot.utils import Singleton
from bot import OperationalException
from bot.context.bot_state import BotState


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

    _analyzed_data: DataFrame = None
    _raw_data_sources: Dict[str, DataFrame] = None

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
        self._state.run()

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
    def raw_data(self) -> Dict[str, DataFrame]:
        return self._raw_data_sources

    @raw_data.setter
    def raw_data(self, raw_data_sources: Dict[str, DataFrame]) -> None:
        self._raw_data_sources = raw_data_sources

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
