import logging
from typing import List, Dict, Any

from bot.data.data_providers import DataProvider, DataProviderException
from . import add_ticker, get_all_table_names, create_tables, get_company_info

logger = logging.getLogger(__name__)

TABLE_NAMES = ['TICKERS', 'TRADES']


class DataProviderManager:

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

    def add_ticker(self, ticker: str) -> None:

        if get_company_info(ticker, self.__config):
            raise DataProviderException("Ticker {} already exists".format(ticker))
        else:
            for data_provider in self.registered_modules:

                if data_provider.evaluate_ticker(ticker):
                    logger.info("Ticker exists")
                    profile = data_provider.get_profile(ticker)

                    company_name = profile.get('profile', {}).get('companyName', {})
                    industry = profile.get('profile', {}).get('industry', {})

                    if company_name and industry:
                        add_ticker(ticker, company_name, industry, self.__config)
                        logger.info("Ticker {} has been added ...".format(ticker))
                        return

        raise DataProviderException("Could not evaluate ticker {}".format(ticker))



