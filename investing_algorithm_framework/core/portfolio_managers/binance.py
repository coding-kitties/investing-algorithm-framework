from .portfolio_manager import PortfolioManager
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.mixins import \
    BinancePortfolioManagerMixin


class BinancePortfolioManager(BinancePortfolioManagerMixin, PortfolioManager):
    identifier = BINANCE

    def __init__(self, identifier: str = None, trading_currency: str = None):
        super(PortfolioManager, self).__init__(identifier)

        if identifier is not None:
            self.identifier = identifier

        if trading_currency is not None:
            self.trading_currency = trading_currency

    def initialize(self, algorithm_context):
        api_key = algorithm_context.config.get("API_KEY", None)
        secret_key = algorithm_context.config.get("SECRET_KEY", None)

        try:
            self.get_api_key()
        except OperationalException as e:

            if api_key is not None:
                self.api_key = api_key
            else:
                raise e

        try:
            self.get_secret_key()
        except OperationalException as e:

            if secret_key is not None:
                self.secret_key = secret_key
            else:
                raise e

        self.initialize_exchange()
        super(BinancePortfolioManager, self).initialize(algorithm_context)
