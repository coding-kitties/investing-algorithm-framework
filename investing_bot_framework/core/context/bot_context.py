from typing import Type

from investing_bot_framework.core.configuration import settings
from investing_bot_framework.core.exceptions import OperationalException
from investing_bot_framework.core.utils import Singleton
from investing_bot_framework.core.states import BotState


class BotContext(metaclass=Singleton):
    """
    The BotContext defines the current state of the running bot. It also maintains a reference to an instance of a
    BotState subclass, which represents the current state of the BotContext.
    """

    # A reference to the current state of the Bot Context.
    _state: BotState = None

    # Settings reference
    settings = settings

    def register_initial_state(self, bot_state: Type[BotState]) -> None:
        self._state = bot_state(context=self)

    def transition_to(self, bot_state: Type[BotState]) -> None:
        """
        Function to change the running BotState at runtime.
        """
        self._state = bot_state(context=self)

    def _check_state(self, raise_exception: bool = False) -> bool:
        """
        Function that wil check if the state is set
        """

        if self._state is None:

            if raise_exception:
                raise OperationalException(
                    "Bot context doesn't have a state. Make sure that you set the state of bot either "
                    "by initializing it or making sure that you transition to a new valid state."
                )
            else:
                return False

        return True

    def start(self) -> None:
        """
        Run the current state of the investing_bot_framework
        """

        self._check_state(raise_exception=True)
        self._run_state()

        while self._check_state():
            self._run_state()

    def _run_state(self) -> None:
        self._state.start()
        transition_state = self._state.get_transition_state_class()
        self.transition_to(transition_state)

