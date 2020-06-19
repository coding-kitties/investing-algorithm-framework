import os
import sys

from investing_algorithm_framework.core.management import BaseCommand
from investing_algorithm_framework.core.resolvers import ClassCollector
from investing_algorithm_framework.core.management.utils import get_commands
from investing_algorithm_framework.core.management.commands.help import HelpCommand


class ManagementUtility:
    """
    Encapsulate the logic of the django-admin and manage.py utilities.
    """

    def __init__(self, argv=None) -> None:
        self.argv = argv or sys.argv[:]
        self.program_name = os.path.basename(self.argv[0])

        if self.program_name == '__main__.py':
            self.program_name = 'python -m investing-investing_algorithm_framework'
        self.settings_exception = None

    def execute(self) -> None:
        """
        Given the command-line arguments, figure out which sub command is being
        run, create a parser appropriate to that command, and run it.
        """

        try:
            sub_command = self.argv[1]
        except IndexError:
            sub_command = 'help'  # Display help by default if no arguments are given.

        # Run the command if it is not a help command
        if sub_command != 'help':
            response = self.fetch_command(sub_command).run_from_argv(self.argv)
        else:
            # Help for sub command
            if len(self.argv) > 2:

                # make the first argument the sub command and the second argument the help option
                sub_command = self.argv[2]
                option = '--help'

                self.argv[1] = sub_command
                self.argv[2] = option
                response = self.fetch_command(sub_command).run_from_argv(self.argv)
            else:
                # Show general help command
                command = HelpCommand()
                response = command.run_from_argv(self.argv)

        sys.stdout.write(response)

    def fetch_command(self, sub_command: str) -> BaseCommand:
        commands = get_commands()
        app_name = commands[sub_command]

        collector = ClassCollector(
            '{}.management.commands'.format(app_name),
            class_type=BaseCommand,
            module_name=sub_command
        )

        command_instance = collector.instances[0]
        return command_instance


def execute_from_command_line(argv=None):

    """Run the ManagementUtility."""
    utility = ManagementUtility(argv)
    utility.execute()