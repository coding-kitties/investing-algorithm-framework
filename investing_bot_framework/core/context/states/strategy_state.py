from typing import Type
from investing_bot_framework.core.context.states import BotState


class StrategyState(BotState):

    def run(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def reconfigure(self) -> None:
        pass

    def update(self, observable, **kwargs) -> None:
        pass

    def get_transition_state_class(self) -> Type:
        from investing_bot_framework.core.context.states.data_state import DataState
        return DataState
