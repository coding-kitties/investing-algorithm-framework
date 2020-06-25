from typing import Type

from investing_algorithm_framework.configuration import settings
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.utils import Singleton
from investing_algorithm_framework.core.state import State


class Context(metaclass=Singleton):
    """
    The Context defines the current state of the running algorithms. It
    also maintains a reference to an instance of a state subclass, which
    represents the current state of the context instance.
    """

    # A reference to the current state of the context.
    _state: State = None

    # Settings reference
    settings = settings

    def register_initial_state(self, state: Type[State]) -> None:
        self._state = state(context=self)

    def transition_to(self, bot_state: Type[State]) -> None:
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
                    "Context doesn't have a state. Make sure that you set "
                    "the state either by initializing it or making sure that "
                    "you transition to a new valid state."
                )
            else:
                return False

        return True

    def start(self) -> None:
        """
        Run the current state of the investing_algorithm_framework
        """

        self._check_state(raise_exception=True)
        self._run_state()

        while self._check_state():
            self._run_state()

    def _run_state(self) -> None:
        self._state.start()
        transition_state = self._state.get_transition_state_class()
        self.transition_to(transition_state)
