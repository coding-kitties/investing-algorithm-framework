import logging
import concurrent.futures
from typing import List, Dict, Any

from bot.data.data_providers import DataProvider, DataProviderException
from . import get_all_table_names, create_tables

from bot.utils import singleton

logger = logging.getLogger(__name__)

TABLE_NAMES = ['TICKERS', 'TRADES']


@singleton
class DataProviderManager:
    """
    DataProviderManager handles all data providers
    """

    def __init__(self, config: Dict[str, Any]) -> None:

        self.__config = config

        if TABLE_NAMES != get_all_table_names(self.__config):
            create_tables(self.__config)

        logger.info("Starting all data providers ...")

        """ Initializes all enabled service modules """
        self.registered_modules: List[DataProvider] = []

        # Enable fmp data provider
        if self.__config.get('data_providers', {}).get('fmp', {}).get('enabled', False):
            logger.info('Enabling data_provider.fmp ...')
            from bot.data.data_providers.fmp_data_provider import FMPDataProvider
            self.registered_modules.append(FMPDataProvider(self.__config))

    def evaluate_ticker(self, ticker: str) -> bool:

        for data_provider in self.registered_modules:

            if data_provider.evaluate_ticker(ticker):
                logger.info("Ticker exists")
                return True

        return False

    def get_profile(self, ticker: str) -> Dict:

        for data_provider in self.registered_modules:

            profile = data_provider.get_profile(ticker)

            if profile:
                return profile

        raise DataProviderException("Could not profile for {}".format(ticker))

    def start_data_providers(self):

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:

            for data_providers in self.registered_modules:
                executor.submit(data_providers.scrape_data())



