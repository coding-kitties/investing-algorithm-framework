import logging
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from bot import __version__
from bot import constants
from bot import DependencyException

logger = logging.getLogger(__name__)


class Argument:

    def __init__(self, *args, **kwargs):
        self.cli = args
        self.kwargs = kwargs


# Declarations of the command line interface commands
CLI_COMMANDS = {
    "version": Argument(
        '-V', '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    ),
    "config": Argument(
        '-c', '--config',
        help="Specify configuration file (default: {}".format(constants.DEFAULT_CONFIG),
        action='append',
        metavar='PATH',
    ),
}


class Arguments:
    """
    Arguments Class. Functions as a utilities class to manage the arguments received by the command line interface,
    """

    def __init__(self, args: Optional[List[str]]) -> None:
        self.args = args
        self._parsed_args: Optional[argparse.Namespace] = None
        self.parser = argparse.ArgumentParser()

    @property
    def parsed_args(self) -> Dict[str, Any]:
        """
        Returnn the list of arguments
        :return: List[str] List of arguments
        """

        if self._parsed_args is None:
            self.build_args()
            self._parsed_args = self._parse_args()

        return vars(self._parsed_args)

    def _parse_args(self) -> argparse.Namespace:
        """
        Parses given arguments and returns an argparse Namespace instance.
        """
        parsed_arg = self.parser.parse_args(self.args)

        if 'config' in parsed_arg and parsed_arg.config is None or (Path.cwd() / constants.DEFAULT_CONFIG).is_file():
            parsed_arg.config = [constants.DEFAULT_CONFIG]
        else:
            raise DependencyException("config.json file is not specified, "
                                      "please see the configuration section in the docs")

        return parsed_arg

    def build_args(self):

        for command in CLI_COMMANDS:
            argument = CLI_COMMANDS[command]
            self.parser.add_argument(*argument.cli, dest=command, **argument.kwargs)

