from typing import Type, List

from investing_bot_framework.core.configuration import settings
from investing_bot_framework.core.exceptions import OperationalException
from investing_bot_framework.core.utils import Singleton
from investing_bot_framework.core.context.states import BotState
from investing_bot_framework.core.data.data_providers import DataProvider


class BotContext(metaclass=Singleton):
    """
    The BotContext defines the current state of the running investing_bot_framework. It also maintains a reference to an instance of a
    BotState subclass, which represents the current state of the BotContext.
    """

    # A reference to the current state of the Bot Context.
    _state: BotState = None

    # List of data providers
    _data_providers: List[DataProvider] = []

    # Settings reference
    settings = settings

    def initialize(self, bot_state: Type[BotState]) -> None:

        # Stop the current state of the investing_bot_framework
        if self._state:
            self._state.stop()

        self._state = bot_state(context=self)

    def transition_to(self, bot_state: Type[BotState]) -> None:
        """
        The Context allows changing the State object at runtime.
        """

        self._state = bot_state(context=self)

    def _check_state(self) -> None:
        """
        Function that wil check if the state is set
        """

        if self._state is None:
            raise OperationalException(
                "Bot context doesn't have a state, Make sure that you set the state of investing_bot_framework either by initializing it "
                "or making sure that you transition to a new valid state."
            )

    def run(self) -> None:
        """
        Run the current state of the investing_bot_framework
        """

        self._check_state()
        self._state.start()

    def stop(self) -> None:
        """
        Stop the current state of the investing_bot_framework
        """

        self._check_state()
        self._state.stop()

    def reconfigure(self) -> None:
        """
        Reconfigure the current state of the investing_bot_framework
        """

        self._check_state()
        self._state.reconfigure()