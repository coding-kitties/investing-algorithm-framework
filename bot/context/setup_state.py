import logging

from bot.context.bot_state import BotState
from bot.context.bot_context import BotContext
from bot.context.data_providing_state import DataProvidingState

logger = logging.getLogger(__name__)


class SetupState(BotState):

    def __init__(self):
        super(SetupState, self).__init__()

        logger.info("Initializing setup state ...")

    def run(self):
        logger.info("Setup state started ...")

        # Configure and start all the services

        logger.info("Transitioning to data providing state ...")
        context = BotContext()
        context.transition_to(DataProvidingState)

    def stop(self):
        # Stopping all services
        pass

    def reconfigure(self):
        # Clean up and reconfigure all the services
        pass
