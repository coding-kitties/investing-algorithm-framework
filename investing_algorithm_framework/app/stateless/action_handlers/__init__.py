from enum import Enum

from investing_algorithm_framework.app.stateless.action_handlers \
    .check_online_handler import CheckOnlineHandler
from investing_algorithm_framework.app.stateless.action_handlers \
    .run_strategy_handler import RunStrategyHandler
from investing_algorithm_framework.core.exceptions import OperationalException


class Action(Enum):
    RUN_STRATEGY = 'RUN_STRATEGY'
    CHECK_ONLINE = "CHECK_ONLINE"

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
    strategy = None

    @staticmethod
    def of(payload: dict):
        action_handler = ActionHandler()
        action_handler.set_strategy(payload)
        return action_handler

    def handle(self, payload, algorithm_context):
        return self.strategy.handle_event(
            payload=payload, algorithm_context=algorithm_context
        )

    def set_strategy(self, payload):
        action = ActionHandler.get_action_type(payload)

        if Action.RUN_STRATEGY.equals(action):
            self.strategy = RunStrategyHandler()
        elif Action.CHECK_ONLINE.equals(action):
            self.strategy = CheckOnlineHandler()
        else:
            raise OperationalException("Action not supported")

    @staticmethod
    def get_action_type(payload):

        if "action" in payload:
            action = payload["action"]
        else:
            action = payload["ACTION"]

        if action is None:
            raise OperationalException("Action type not supported")

        return action
