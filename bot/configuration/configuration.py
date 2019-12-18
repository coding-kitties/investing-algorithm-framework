import logging

from typing import Any, Dict, List, Optional

from bot.configuration.load_config import load_config_file
logger = logging.getLogger(__name__)


class Configuration:
    """
    Class to read and init the bot configuration
    """

    def __init__(self, args: Dict[str, Any]) -> None:
        self.args = args
        self.config: Optional[Dict[str, Any]] = None

    def get_config(self) -> Dict[str, Any]:
        """
        Return the config. Use this method to get the bot config
        :return: Dict: Bot config
        """
        if self.config is None:
            self.config = self.load_config()

        return self.config

    @staticmethod
    def load_from_files(files: List[str]) -> Dict[str, Any]:

        config = {}

        # We expect here a list of config filenames
        for path in files:
            logger.info(f'Using config: {path} ...')

            # Merge config options, overwriting old values
            config = load_config_file(path)

        return config

    def load_config(self) -> Dict[str, Any]:
        """
        Extract information for sys.argv and load the bot configuration
        :return: Configuration dictionary
        """
        # Load all configs
        config: Dict[str, Any] = self.load_from_files(self.args.get("config", []))

        return config
