from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.portfolio_managers.binance import \
    BinancePortfolioManager


class DefaultPortfolioManagerFactory:

    @staticmethod
    def of_market(market):

        if market.upper() == BINANCE:
            return BinancePortfolioManager()

        return None
