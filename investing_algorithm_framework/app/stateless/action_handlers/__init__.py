from investing_algorithm_framework import OperationalException
from investing_algorithm_framework.app.stateless.action_handlers\
    .run_strategy_handler import RunStrategyHandler

from enum import Enum


class Action(Enum):
    RUN_STRATEGY = 'RUN_STRATEGY'

    @staticmethod
    def from_value(value: str):
        if isinstance(value, Action):
            for action in Action:

                if value == action:
                    return action

        if isinstance(value, str):
            return Action.from_string(value)

        raise ValueError("Could not convert value to action")

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for action in Action:

                if value.upper() == action.value:
                    return action

        raise ValueError("Could not convert value to action")

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return Action.from_string(other) == self


class ActionHandler:
    handle_strategy = None

    @staticmethod
    def of(action: Action):
        action_handler = ActionHandler()
        action_handler._set_strategy(action)
        return action_handler

    def handle(self, payload=None):
        return self.handle_strategy.handle_event(payload)

    def _set_strategy(self, action):

        if Action.RUN_STRATEGY.equals(action):
            self.handle_strategy = RunStrategyHandler()

        raise OperationalException("Action not supported")
