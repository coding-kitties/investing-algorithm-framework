import os
import sys
from colorama import Fore

from investing_algorithm_framework.management import BaseCommand
from investing_algorithm_framework.core.resolvers import ClassResolver
from investing_algorithm_framework.management.utils import get_commands
from investing_algorithm_framework.management.commands.help import HelpCommand
from investing_algorithm_framework.core.exceptions import OperationalException


class ManagementUtility:
    """
    Encapsulate the logic of the django-admin and manage.py-template utilities.
    """

    def __init__(self, argv=None) -> None:
        self.argv = argv or sys.argv[:]
        self.program_name = os.path.basename(self.argv[0])

        if self.program_name == '__main__.py':
            self.program_name = 'python -m ' \
                                'investing-investing_algorithm_framework'
        self.settings_exception = None

    def execute(self) -> None:
        """
        Given the command-line arguments, figure out which sub command is being
        run, create a parser appropriate to that command, and run it.
        """

        try:
            sub_command = self.argv[1]
        except IndexError:
            # Display help by default if no arguments are given.
            sub_command = 'help'

        try:
            # Run the command if it is not a help command
            if sub_command.lower() not in [
                'help', '-help', '--help', 'h', '-h'
            ]:
                response = self.fetch_command(sub_command).\
                    run_from_argv(self.argv)
            else:
                # Help for sub command
                if len(self.argv) > 2:

                    # make the first argument the sub command and the second
                    # argument the help option
                    sub_command = self.argv[2]
                    option = '--help'

                    self.argv[1] = sub_command
                    self.argv[2] = option
                    response = self.fetch_command(sub_command)\
                        .run_from_argv(self.argv)
                else:
                    # Show general help command
                    command = HelpCommand()
                    response = command.run_from_argv(self.argv)
        except Exception as e:
            response = format_error_message(str(e))

        sys.stdout.write(response)

    @staticmethod
    def fetch_command(sub_command: str) -> BaseCommand:
        commands = get_commands()

        if sub_command not in commands:
            raise OperationalException("Command was not found")

        app_name = commands[sub_command]

        collector = ClassResolver(
            '{}.commands'.format(app_name),
            class_type=BaseCommand,
            module_name=sub_command
        )

        command_instance = collector.instances[0]
        return command_instance


def format_success_message(message: str) -> str:
    """
    Utility function to format a success message
    """

    if message is None:
        return Fore.GREEN + "Process finished" + '\n'

    return Fore.GREEN + message + '\n'


def format_error_message(message: str) -> str:
    """
    Utility function to format an error message
    """

    if message is None:
        return Fore.RED + 'Error occurred' + '\n'

    return Fore.RED + message + '\n'


def execute_from_command_line(argv=None):

    """Run the ManagementUtility."""
    utility = ManagementUtility(argv)
    utility.execute()
