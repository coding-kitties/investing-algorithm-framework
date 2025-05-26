from enum import Enum

from investing_algorithm_framework.app.stateless.action_handlers \
    .check_online_handler import CheckOnlineHandler
from investing_algorithm_framework.app.stateless.action_handlers \
    .run_strategy_handler import RunStrategyHandler
from investing_algorithm_framework.domain.exceptions import \
    OperationalException


class StatelessAction(Enum):
    RUN_STRATEGY = 'RUN_STRATEGY'
    PING = "PING"

    @staticmethod
    def from_value(value: str):
        if isinstance(value, StatelessAction):
            for action in StatelessAction:

                if value == action:
                    return action

        if isinstance(value, str):
            return StatelessAction.from_string(value)

        raise ValueError("Could not convert value to stateless action")

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for action in StatelessAction:

                if value.upper() == action.value:
                    return action

        raise ValueError("Could not convert value to stateless action")

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return StatelessAction.from_string(other) == self


class ActionHandler:
    strategy = None

    @staticmethod
    def of(payload: dict):
        action_handler = ActionHandler()
        action_handler.set_strategy(payload)
        return action_handler

    def handle(self, payload, context, strategy_orchestrator_service):
        return self.strategy.handle_event(
            payload, context, strategy_orchestrator_service
        )

    def set_strategy(self, payload):
        action = ActionHandler.get_action_type(payload)

        if StatelessAction.RUN_STRATEGY.equals(action):
            self.strategy = RunStrategyHandler()
        elif StatelessAction.PING.equals(action):
            self.strategy = CheckOnlineHandler()
        else:
            raise OperationalException("Action not supported")

    @staticmethod
    def get_action_type(payload):

        if payload is None or \
                ("ACTION" not in payload and "action" not in payload):
            raise OperationalException("Action type is not defined")

        if "action" in payload:
            action = payload["action"]
        else:
            action = payload["ACTION"]

        return action
