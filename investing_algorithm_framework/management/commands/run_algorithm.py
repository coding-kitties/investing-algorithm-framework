from typing import Any

from investing_algorithm_framework.management.command import BaseCommand
from investing_algorithm_framework.core.context import Context
from investing_algorithm_framework.configuration.config_constants import \
    SETTINGS_CONTEXT_CONFIGURATION


class RunAlgorithmCommand(BaseCommand):
    help_message = "Runs an instance of an algorithm created with the " \
                   "investing_algorithm_framework."

    success_message = "Algorithm is finished running."

    def add_arguments(self, parser) -> None:
        pass

    def handle(self, *args, **options) -> Any:
        # Call the context
        context = Context()

        # configure the configuration
        context.config.configure()

        # Load the context configuration
        __import__(context.config[SETTINGS_CONTEXT_CONFIGURATION])

        # run the context
        context.start()
