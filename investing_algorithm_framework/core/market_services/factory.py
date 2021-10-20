from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.market_services\
    .binance_market_service import BinanceMarketService


class DefaultMarketServiceFactory:

    @staticmethod
    def of_market(market):
        if market.upper() == BINANCE:
            return BinanceMarketService()

        return None
