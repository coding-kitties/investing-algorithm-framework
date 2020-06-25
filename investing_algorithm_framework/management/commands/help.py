from typing import Any
from collections import defaultdict

from investing_algorithm_framework.management import BaseCommand
from investing_algorithm_framework.management.utils import get_commands
from investing_algorithm_framework.configuration.config_constants import \
    FRAMEWORK_CORE_MODULE_NAME, FRAMEWORK_NAME


class HelpCommand(BaseCommand):
    """
    Default help command if there is no sub command specified
    """

    def add_arguments(self, parser) -> None:
        pass

    def handle(self) -> Any:
        usage = [
            "",
            "This is the command line management for the investing "
            "algorithm framework. \n"
            "Type help <sub_command>' for help on a specific sub command.",
            "",
            "Available sub commands:",
        ]

        # The command list will be entries based on app name with
        # corresponding commands list
        commands_dict = defaultdict(lambda: [])

        for name, app in get_commands().items():

            # Change the module name to the framework name for
            # nice presentation
            if app == FRAMEWORK_CORE_MODULE_NAME:
                app = FRAMEWORK_NAME

            commands_dict[app].append(name)

        for app in sorted(commands_dict):
            usage.append("")
            usage.append(("[{}]".format(app)))

            for name in sorted(commands_dict[app]):
                usage.append("      {}".format(name))

        usage.append("")
        return '\n'.join(usage)

    def run_from_argv(self, argv):
        # Overwrite because we don't need to pass any arguments

        return self.execute()
