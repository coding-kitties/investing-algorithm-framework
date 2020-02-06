from typing import Any

from bot.core.management.command import BaseCommand, CommandError
from bot.core.configuration import settings
from bot.core.context import BotContext
from bot.core.context.states.setup_state import SetupState


class RunBotCommand(BaseCommand):
    help_message = (
        "Runs a bot, by default it will run until stopped, if cycles is specified it will run the according to "
        "the amount of cycles"
    )

    success_message = (
        "Bot is finished running"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--cycles',
            help='Optional number for the amount of cycles the bot runs'
        )

    def handle(self, *args, **options) -> Any:

        # Load the settings
        if not settings.configured:
            raise CommandError(
                "Settings module is not specified, make sure you have setup a bot project and the bot is valid or that "
                "you have specified the settings module in your manage.py file"
            )

        cycles = options.get('name', None)

        # Load all the components of the bot
        # data_providers_loader = DataProvidersLoader()
        # data_providers = data_providers_loader.load_modules()

        # Create an bot context of the bot and run it
        context = BotContext()
        context.initialize(SetupState)
        context.run()




