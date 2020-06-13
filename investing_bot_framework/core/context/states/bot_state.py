from abc import ABC, abstractmethod
from typing import List

from investing_bot_framework.core.context.state_validator import StateValidator


class BotState(ABC):
    """
    Represents a state of the Bot, these states are use by the BotContext. Each implemented state represents a work
    mode for the investing_bot_framework.
    """

    # Transition state for the next BotState
    transition_state_class = None

    # Validator for the current state
    state_validators = None

    def __init__(self, context, state_validator: StateValidator = None) -> None:
        self._bot_context = context
        self._state_validator = state_validator

    def start(self):

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

    def validate_state(self) -> bool:
        """
        Function that will validate the state
        """

        state_validators = self.get_state_validators()

        if state_validators is None:
            return True

        for state_validator in state_validators:

            if not state_validator.validate_state(self):
                return False

        return True

    def get_transition_state_class(self):

        assert getattr(self, 'transition_state_class', None) is not None, (
            "{} should either include a transition_state_class attribute, or override the "
            "`get_transition_state_class()`, method.".format(self.__class__.__name__)
        )

        return self.transition_state_class

    def get_state_validators(self) -> List[StateValidator]:

        if self.state_validators is not None:
            return [
                state_validator() for state_validator in getattr(self, 'state_validators')
                if issubclass(state_validator, StateValidator)
            ]


