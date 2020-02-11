from typing import Any

from investing_bot_framework.core.management.command import BaseCommand, CommandError
from investing_bot_framework.core.context import BotContext
from investing_bot_framework.core.context.states.setup_state import SetupState


class RunBotCommand(BaseCommand):
    help_message = (
        "Runs a investing_bot_framework, by default it will run until stopped, if cycles is specified it will run the according to "
        "the amount of cycles"
    )

    success_message = (
        "Bot is finished running"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--cycles',
            help='Optional number for the amount of cycles the investing_bot_framework runs'
        )

    def handle(self, *args, **options) -> Any:

        cycles = options.get('name', None)

        # Create an investing_bot_framework context of the investing_bot_framework and run it
        context = BotContext()
        context.initialize(SetupState)
        context.start()

    @staticmethod
    def validate_cycles(self, cycles: int) -> None:

        if cycles is not None and cycles < 1:
            raise CommandError("Given cycles arguments is smaller then 1")




