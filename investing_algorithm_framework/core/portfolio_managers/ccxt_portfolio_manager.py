from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.mixins import \
    BinancePortfolioManagerMixin
from investing_algorithm_framework.core.portfolio_managers \
    import SQLLitePortfolioManager, PortfolioManager


class CCXTPortfolioManager(
    BinancePortfolioManagerMixin, PortfolioManager
):
    def __init__(self, identifier: str = None, trading_symbol: str = None):
        super(CCXTPortfolioManager, self).__init__(identifier)

        if identifier is not None:
            self.identifier = identifier

        if trading_symbol is not None:
            self.trading_symbol = trading_symbol


class CCXTSQLitePortfolioManager(
    BinancePortfolioManagerMixin, SQLLitePortfolioManager
):
    def __init__(self, identifier: str = None, trading_symbol: str = None):
        super(CCXTSQLitePortfolioManager, self).__init__(identifier)

        if identifier is not None:
            self.identifier = identifier

        if trading_symbol is not None:
            self.trading_symbol = trading_symbol
