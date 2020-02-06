from typing import Any

from bot.core.management.command import BaseCommand, CommandError
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

        cycles = options.get('name', None)

        # Create an bot context of the bot and run it
        context = BotContext()
        context.initialize(SetupState)
        context.run()

    @staticmethod
    def validate_cycles(self, cycles: int) -> None:

        if cycles is not None and cycles < 1:
            raise CommandError("Given cycles arguments is smaller then 1")




