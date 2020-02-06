import time
from typing import List
from wrapt import synchronized

from bot.core.events import Observer
from bot.core.context.bot_context import BotContext
from bot.core.context.states import BotState


class DataProvidingState(BotState, Observer):

    def __init__(self, context: BotContext) -> None:
        super(DataProvidingState, self).__init__(context)

        self._updated = False
        self._started = False

    def _initialize(self) -> None:
        pass

    def _clean_up(self) -> None:
        pass

    def run(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def reconfigure(self) -> None:
        pass

    @synchronized
    def update(self, observable, **kwargs) -> None:
        self._updated = True
