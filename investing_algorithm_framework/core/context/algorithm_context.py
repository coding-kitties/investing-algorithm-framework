import inspect

from investing_algorithm_framework.configuration import ContextConfiguration
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.utils import Singleton
from investing_algorithm_framework.core.state import State


class AlgorithmContext(metaclass=Singleton):
    """
    The AlgorithmContext defines the current state of a running algorithms. It
    also maintains a reference to an instance of a state subclass, which
    represents the current state of the algorithm instance.
    """

    # A reference to the current state of the context.
    _state: State = None

    # Settings reference
    _config = ContextConfiguration()

    def register_initial_state(self, state) -> None:
        self._transition(state)

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
        self._transition(transition_state)

    def _transition(self, transition_state) -> None:

        # A class has been provided as State
        if inspect.isclass(transition_state):

            # Check if subclass of State class
            if issubclass(transition_state, State):
                self._state = transition_state(self)
            else:

                if not callable(getattr(transition_state, "run", None)):
                    raise OperationalException(
                        "Provided state class has no run method"
                    )

                self._state = transition_state()
        else:
            self._state = transition_state

    @property
    def config(self) -> ContextConfiguration:
        return self._config
