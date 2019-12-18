import logging
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from bot.configuration.cli_options import AVAILABLE_CLI_OPTIONS
from bot import constants
from bot import DependencyException

logger = logging.getLogger(__name__)


ARGS_COMMON = ["version", "config"]


class Arguments:
    """
    Arguments Class. Manage the arguments received by the cli
    """

    def __init__(self, args: Optional[List[str]]) -> None:

        # Map the args
        self.args = args
        self._parsed_arg: Optional[argparse.Namespace] = None

    def get_parsed_arg(self) -> Dict[str, Any]:
        """
        Return the list of arguments
        :return: List[str] List of arguments
        """

        if self._parsed_arg is None:
            self._build_sub_commands()
            self._parsed_arg = self._parse_args()

        return vars(self._parsed_arg)

    def _parse_args(self) -> argparse.Namespace:
        """
        Parses given arguments and returns an argparse Namespace instance.
        """
        parsed_arg = self.parser.parse_args(self.args)

        # Workaround issue in argparse with action='append' and default value
        # (see https://bugs.python.org/issue16399)
        # Allow no-config for certain commands (like downloading / plotting)

        if 'config' in parsed_arg and parsed_arg.config is None and (Path.cwd() / constants.DEFAULT_CONFIG).is_file():
            parsed_arg.config = [constants.DEFAULT_CONFIG]
        else:
            raise DependencyException("config.json file is not specified, "
                                      "please see the configuration section in the docs")

        return parsed_arg

    @staticmethod
    def _build_args(option_list, parser):

        for val in option_list:
            opt = AVAILABLE_CLI_OPTIONS[val]
            parser.add_argument(*opt.cli, dest=val, **opt.kwargs)

    def _build_sub_commands(self) -> None:
        """
        Builds and attaches all sub commands.
        :return: None
        """

        # Build main command
        self.parser = argparse.ArgumentParser(description="Trading bot based on value principles")
        self._build_args(option_list=ARGS_COMMON, parser=self.parser)

