import logging
from typing import Dict, Any

from bot.configuration.configuration import Configuration
from bot.context.bot_context import BotContext
from bot.context.setup_state import SetupState


logger = logging.getLogger(__name__)


def initialize(args: Dict[str, Any]) -> int:
    logger.info("Initializing bot ...")

    # Create the configuration
    config = Configuration.create_config(args)

    context = BotContext()
    context.config = config.config

    # Initialize context with SetupState
    context.initialize(SetupState)

    try:
        context.run()
    except KeyboardInterrupt:
        logger.info('SIGINT received, aborting ...')

    return 0

