from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.mixins import \
    BinancePortfolioManagerMixin
from investing_algorithm_framework.core.portfolio_managers\
    .sqllite_portfolio_manager import SQLLitePortfolioManager


class BinancePortfolioManager(
    BinancePortfolioManagerMixin, SQLLitePortfolioManager
):
    identifier = BINANCE
    market = BINANCE

    def __init__(self, identifier: str = None, trading_symbol: str = None):
        super(BinancePortfolioManager, self).__init__(identifier)

        if identifier is not None:
            self.identifier = identifier

        if trading_symbol is not None:
            self.trading_symbol = trading_symbol
