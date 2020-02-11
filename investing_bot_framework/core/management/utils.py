import os
import pkgutil
import functools
from typing import Dict, List

from investing_bot_framework.core.resolvers import ClassCollector
from investing_bot_framework.core.management.command import BaseCommand
from investing_bot_framework.core.configuration import settings
from investing_bot_framework.core.configuration.config_constants import SETTINGS_MODULE_PATH_ENV_NAME

# Load the settings
settings = settings


def find_commands(management_dir: str) -> List[str]:
    """
    Given a path to a management directory, return a list of all the command
    names that are available.
    """

    command_dir = os.path.join(management_dir, 'commands')
    return [name for _, name, is_pkg in pkgutil.iter_modules([command_dir])
            if not is_pkg and not name.startswith('_')]


@functools.lru_cache(maxsize=None)
def get_commands() -> Dict[str, str]:
    """
    Returns a list of all the available commands for the installed apps
    """

    # Base commands
    commands = {name: 'investing_bot_framework.core' for name in find_commands(os.path.join(os.path.dirname(__file__)))}

    if not settings.configured:
        return commands

    # Load all the commands from the installed apps
    return commands


def load_command(app_dir: str, sub_command: str) -> BaseCommand:
    """
    Given a command name and an application name, return the Command
    class instance.
    """

    collector = ClassCollector(
        '{}.management.commands'.format(app_dir),
        class_type=BaseCommand,
        module_name=sub_command
    )

    return collector.instances[0]