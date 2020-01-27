import os
import sys
import pkgutil
import functools

from bot.core.resolvers import ClassCollector
from bot.core.management.command import BaseCommand


def find_commands(management_dir: str):
    """
    Given a path to a management directory, return a list of all the command
    names that are available.
    """

    command_dir = os.path.join(management_dir, 'commands')
    return [name for _, name, is_pkg in pkgutil.iter_modules([command_dir])
            if not is_pkg and not name.startswith('_')]


def load_command(app_dir: str, sub_command: str):
    """
    Given a command name and an application name, return the Command
    class instance. Allow all errors raised by the import process
    (ImportError, AttributeError) to propagate.
    """

    collector = ClassCollector(
        '{}.management.commands'.format(app_dir),
        class_type=BaseCommand,
        module_name=sub_command
    )

    return collector.instances[0]


@functools.lru_cache(maxsize=None)
def get_commands():
    """
    Return a dictionary mapping command names to their callback applications.
    Look for a management.commands package in django.core, and in each
    installed application -- if a commands package exists, register all
    commands in that package.

    Core commands are always included. If a settings module has been
    specified, also include user-defined commands.

    The dictionary is in the format {command_name: app_name}. Key-value
    pairs from this dictionary can then be used in calls to
    load_command_class(app_name, command_name)

    If a specific version of a command must be loaded (e.g., with the
    startapp command), the instantiated module can be placed in the
    dictionary in place of the application name.

    The dictionary is cached on the first call and reused on subsequent
    calls.
    """

    commands = {name: 'bot.core' for name in find_commands(__path__[0])}

    return commands


class ManagementUtility:
    """
    Encapsulate the logic of the django-admin and manage.py utilities.
    """

    def __init__(self, argv=None) -> None:
        self.argv = argv or sys.argv[:]
        self.program_name = os.path.basename(self.argv[0])

        if self.program_name == '__main__.py':
            self.program_name = 'python -m investing-bot'
        self.settings_exception = None

    def execute(self) -> None:
        """
        Given the command-line arguments, figure out which sub command is being
        run, create a parser appropriate to that command, and run it.
        """

        try:
            sub_command = self.argv[1]
        except IndexError:
            sub_command = 'help'  # Display help if no arguments were given.

        self.fetch_command(sub_command).run_from_argv(self.argv)

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
