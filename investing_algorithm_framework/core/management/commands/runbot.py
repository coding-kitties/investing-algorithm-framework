from typing import Any

from investing_algorithm_framework.core.management.command import BaseCommand, CommandError
from investing_algorithm_framework.core.context import BotContext
from investing_algorithm_framework.core.configuration.config_constants import SETTINGS_BOT_CONTEXT_CONFIGURATION
from investing_algorithm_framework.core.configuration import settings


class RunBotCommand(BaseCommand):
    help_message = (
        "Runs a investing_algorithm_framework, by default it will run until stopped, if cycles is specified it will run "
        "the according to the amount of cycles"
    )

    success_message = (
        "Bot is finished running"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--cycles',
            help='Optional number for the amount of cycles the investing_algorithm_framework runs'
        )

    def handle(self, *args, **options) -> Any:

        # configure settings
        settings.configure()

        # Load the context configuration
        __import__(settings[SETTINGS_BOT_CONTEXT_CONFIGURATION])

        cycles = options.get('name', None)

        # Create an investing_algorithm_framework context of the investing_algorithm_framework and run it
        context = BotContext()
        context.start()

    @staticmethod
    def validate_cycles(self, cycles: int) -> None:

        if cycles is not None and cycles < 1:
            raise CommandError("Given cycles arguments is smaller then 1")




