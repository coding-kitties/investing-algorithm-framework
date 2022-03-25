from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.app.stateless.action_handlers\
    .run_strategy_handler import RunStrategyHandler
from investing_algorithm_framework.configuration.constants import ACTION

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
    def of(payload: dict):
        action_handler = ActionHandler()
        action_handler.set_strategy(payload)
        return action_handler

    def handle(self, payload, algorithm_context):
        return self.handle_strategy.handle_event(
            payload=payload, algorithm_context=algorithm_context
        )

    def set_strategy(self, payload):

        if ACTION not in payload:
            raise OperationalException("Action type is not specified")

        if Action.RUN_STRATEGY.equals(payload[ACTION]):
            self.handle_strategy = RunStrategyHandler()
        else:
            raise OperationalException("Action not supported")
