from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.mixins import \
    BinancePortfolioManagerMixin
from investing_algorithm_framework.core.portfolio_managers import \
    PortfolioManager


class BinancePortfolioManager(BinancePortfolioManagerMixin, PortfolioManager):
    identifier = BINANCE
    market = BINANCE

    def __init__(self, identifier: str = None, trading_currency: str = None):
        super(PortfolioManager, self).__init__(identifier)

        if identifier is not None:
            self.identifier = identifier

        if trading_currency is not None:
            self.trading_currency = trading_currency
