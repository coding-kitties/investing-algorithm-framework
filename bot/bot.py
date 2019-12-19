import logging

from typing import Any, Dict

from bot.data import remove_ticker, get_tickers, add_ticker, get_company_profile
from bot import __version__, OperationalException
from bot.data.data_provider_manager import DataProviderManager

logger = logging.getLogger(__name__)


class Bot:

    def __init__(self, config: Dict[str, Any]) -> None:
        logger.info('Starting bot version %s', __version__)

        # Make variables private, only bot should change them
        self.__config = config
        self.__data_provider_manager = DataProviderManager(self.config)

        # Load tickers
        self._load_tickers()

    @property
    def config(self) -> Dict[str, Any]:
        return self.__config

    def set_config(self, config: Dict[str, Any]):
        self.__config = config

    def _load_tickers(self):
        logger.info("Initializing provided tickers from config ...")
        tickers = self.__config.get('tickers', [])

        for ticker in tickers:

            try:
                self.add_ticker(ticker)
            except OperationalException as e:
                logger.error(str(e))
                continue

    def add_ticker(self, ticker: str) -> None:
        logger.info("Adding ticker ...")

        if not get_company_profile(ticker, self.config):

            if self.__data_provider_manager.evaluate_ticker(ticker):

                profile = self.__data_provider_manager.get_profile(ticker)

                if not profile:
                    raise OperationalException("Could not evaluate {} with the data providers".format(ticker))

                company_name = profile.get('profile', {}).get('companyName', None)
                category = profile.get('profile', {}).get('industry', None)

                if not company_name:
                    raise OperationalException("Could not evaluate company name for ticker {} with the data providers")

                if not company_name:
                    raise OperationalException("Could not evaluate category for ticker {} with the data providers")

                try:
                    add_ticker(
                        ticker,
                        company_name=company_name,
                        category=category,
                        config=self.config
                    )
                except Exception:
                    raise OperationalException(
                        "Something went wrong with adding ticker {} to the registry".format(ticker)
                    )
            else:
                raise OperationalException("Could not evaluate ticker {} with the data providers".format(ticker))
        else:
            raise OperationalException(
                "Ticker {} is already present in registry".format(ticker)
            )

    def remove_ticker(self, ticker: str) -> None:
        logger.info("Removing ticker ...")

        if get_company_profile(ticker, self.config):

            try:
                remove_ticker(ticker, self.config)
            except Exception:
                raise OperationalException("Something went wrong while deleting the ticker from the registry")
        else:
            raise OperationalException("Provided ticker {} does not exist".format(ticker))

    def list_tickers(self):
        logger.info("Listing tickers ...")
        return get_tickers(self.config)



