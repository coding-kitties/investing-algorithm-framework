from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.order_executors.binance \
    import BinanceOrderExecutor


class DefaultOrderExecutorFactory:

    @staticmethod
    def of_market(market):

        if market.upper() == BINANCE:
            return BinanceOrderExecutor()

        return None
