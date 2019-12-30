import os
import logging

from typing import Any, Dict, Optional

from bot import OperationalException
from bot.configuration.load_config import load_config_file

logger = logging.getLogger(__name__)


class Configuration:
    """
    Class to read and initialize the bot configuration
    """

    def __init__(self, args: Dict[str, Any], direct=True) -> None:
        if direct:
            raise OperationalException("Direct creation of Configuration is not allowed")

        self._config: Optional[Dict[str, Any]] = None

        self._initialize(args)

    def _initialize(self, args):
        self._config = load_config_file(args.get('config'))

    @classmethod
    def create_config(cls, args: Dict[str, Any]):

        # Check if all dependencies are met
        if not args['config']:
            raise OperationalException("Config file is not specified")

        config_file = args['config']

        if not os.path.isfile(config_file):
            raise OperationalException("Specified config location is not a file")

        if not config_file.endswith('.json'):
            raise OperationalException("Specified config file is not a JSON file")

        logger.info("Using configuration file: {}".format(config_file))
        return Configuration(args, direct=False)

    @property
    def config(self) -> Dict[str, Any]:
        """
        Return the config.
        """
        return self._config
