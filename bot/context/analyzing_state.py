import logging

from bot.context.bot_state import BotState
from bot.context.bot_context import BotContext

logger = logging.getLogger(__name__)


class AnalyzingState(BotState):

    def __init__(self):
        logger.info("Initializing analyzing state ...")

    def run(self) -> None:
        logger.info("Analyzing state started ...")

        from bot.context.data_providing_state import DataProvidingState
        context = BotContext()
        context.transition_to(DataProvidingState)
        context.run()

    def stop(self) -> None:
        pass

    def reconfigure(self) -> None:
        pass
