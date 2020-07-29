from abc import ABC, abstractmethod
from typing import List

from investing_algorithm_framework.core.validators import StateValidator


class State(ABC):
    """
    Represents a state of the context, these state are use by the Context.
    Each implemented state represents a work mode for a application created
    with investing_algorithm_framework.
    """

    # Transition state for the next BotState
    transition_state_class = None

    # Validator for the current state
    pre_state_validators: List[StateValidator] = None
    post_state_validators: List[StateValidator] = None

    # Flag to classify state as an ending state
    ending_state = False

    def __init__(self, algorithm_context=None) -> None:
        """
        Constructor can be called with algorithm_context being None. This
        is primarily being done for testing reasons.

        Whenever a State instance is submitted to an AlgorithmContext,
        the AlgorithmContext instance passes itself to the state automatically.
        """

        self.algorithm_context = algorithm_context

    def start(self):
        # Will stop the state if pre-conditions are not met
        if not self.validate_state(pre_state=True):
            return

        while True:
            self.run()

            # Will run state again if validation is negative
            if self.validate_state():
                break

    @abstractmethod
    def run(self) -> None:
        pass

    def validate_state(self, pre_state: bool = False) -> bool:
        """
        Function that will validate the state
        """

        if pre_state:
            state_validators = self.get_pre_state_validators()
        else:
            state_validators = self.get_post_state_validators()

        if state_validators is None:
            return True

        for state_validator in state_validators:

            if not state_validator.validate_state(self):
                return False

        return True

    def get_transition_state_class(self):

        if not self.ending_state:

            assert getattr(self, 'transition_state_class', None) is not None, (
                "{} should either include a transition_state_class attribute, "
                "or override the `get_transition_state_class()`, "
                "method.".format(self.__class__.__name__)
            )

        return self.transition_state_class

    def get_pre_state_validators(self) -> List[StateValidator]:

        if self.pre_state_validators is not None:
            return [
                state_validator() for state_validator in getattr(
                    self, 'pre_state_validators'
                ) if issubclass(state_validator, StateValidator)
            ]

    def get_post_state_validators(self) -> List[StateValidator]:

        if self.post_state_validators is not None:
            return [
                state_validator() for state_validator in getattr(
                    self, 'post_state_validators'
                ) if issubclass(state_validator, StateValidator)
            ]
