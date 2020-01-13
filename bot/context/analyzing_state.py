import logging

from bot.context.bot_state import BotState

logger = logging.getLogger(__name__)


class AnalyzingState(BotState):

    def __init__(self, context):
        logger.info("Initializing analyzing state ...")

        super(AnalyzingState, self).__init__(context)

    def run(self) -> None:
        logger.info("Analyzing state started ...")

        from bot.context.data_providing_state import DataProvidingState
        self.context.transition_to(DataProvidingState)
        self.context.run()

    def stop(self) -> None:
        pass

    def reconfigure(self) -> None:
        pass
