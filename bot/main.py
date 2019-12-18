import logging
from typing import Any, List

# Call settings for general configuration
from bot import setup
from bot.configuration import Arguments
from bot.configuration import Configuration
from bot.bot import Bot
from bot.services import ServiceManager

logger = logging.getLogger(__name__)


def main(sysargv: List[str] = None) -> None:
    """
    This function will initiate the bot and start the trading loop.
    :return: None
    """

    arguments = Arguments(sysargv)
    args = arguments.get_parsed_arg()
    configuration = Configuration(args)

    # Setup the bot
    setup.setup_database(configuration.get_config())

    # Create the bot
    bot = Bot(configuration.get_config())

    # Start all the services
    service_manager = ServiceManager(bot)


if __name__ == "__main__":
    main()
