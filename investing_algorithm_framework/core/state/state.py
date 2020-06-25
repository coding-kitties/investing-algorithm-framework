from abc import ABC, abstractmethod
from typing import List

from investing_algorithm_framework.core.validators import StateValidator


class State(ABC):
    """
    Represents a state of the Bot, these state are use by the BotContext.
    Each implemented state represents a work mode for the
    investing_algorithm_framework.
    """

    # Transition state for the next BotState
    transition_state_class = None

    # Validator for the current state
    pre_state_validators: List[StateValidator] = None
    post_state_validators: List[StateValidator] = None

    def __init__(self, context) -> None:
        self._bot_context = context

    def start(self):

        # Will stop the state if pre-conditions are not met
        if not self.validate_state():
            return

        while True:
            self.run()

            # Will run state again if validation is negative
            if self.validate_state():
                break

    @abstractmethod
    def run(self) -> None:
        pass

    @property
    def context(self):
        return self._bot_context

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
