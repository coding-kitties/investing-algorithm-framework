import logging

from typing import Any, Dict

from bot import __version__, OperationalException
from bot.data.data_provider_manager import DataProviderManager
from bot.data.data_providers import DataProviderException

logger = logging.getLogger(__name__)


class Bot:

    def __init__(self, config: Dict[str, Any]) -> None:
        logger.info('Starting bot version %s', __version__)

        # Init objects

        # Make variable private, only bot should change them
        self.__config = config
        self.__data_provider_manager = DataProviderManager(self.config)

    @property
    def config(self) -> Dict[str, Any]:
        return self.__config

    def set_config(self, config: Dict[str, Any]):
        self.__config = config

    def add_ticker(self, ticker: str) -> None:

        try:
            self.__data_provider_manager.add_ticker(ticker)
        except DataProviderException as e:
            raise OperationalException(str(e))



