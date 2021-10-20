from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.mixins import BinanceOrderExecutorMixin
from investing_algorithm_framework.core.order_executors import OrderExecutor


class BinanceOrderExecutor(BinanceOrderExecutorMixin, OrderExecutor):
    identifier = BINANCE

    def __init__(self, identifier: str = None):
        super(BinanceOrderExecutor, self).__init__(identifier)

        if identifier is not None:
            self.identifier = identifier
