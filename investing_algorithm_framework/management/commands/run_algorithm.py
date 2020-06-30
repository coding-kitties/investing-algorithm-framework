from typing import Any

from investing_algorithm_framework.management.command import BaseCommand
from investing_algorithm_framework.core.context import Context
from investing_algorithm_framework.configuration.config_constants import \
    SETTINGS_CONTEXT_CONFIGURATION
from investing_algorithm_framework.configuration import settings


class RunAlgorithmCommand(BaseCommand):
    help_message = "Runs an instance of an algorithm created with the " \
                   "investing_algorithm_framework."

    success_message = "Algorithm is finished running."

    def add_arguments(self, parser) -> None:
        pass

    def handle(self, *args, **options) -> Any:

        # configure settings
        settings.configure()

        # Load the context configuration
        __import__(settings[SETTINGS_CONTEXT_CONFIGURATION])

        # Create an investing_algorithm_framework context of the
        # investing_algorithm_framework and run it
        context = Context()
        context.start()
