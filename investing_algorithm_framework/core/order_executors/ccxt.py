from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.mixins import CCXTOrderExecutorMixin
from investing_algorithm_framework.core.order_executors import OrderExecutor


class CCXTOrderExecutor(CCXTOrderExecutorMixin, OrderExecutor):
    identifier = BINANCE

    def __init__(
        self, identifier, market, trading_symbol, api_key, secret_key
    ):
        super(CCXTOrderExecutor, self).__init__(identifier)
        self.identifier = identifier
        self.trading_symbol = trading_symbol.upper()
        self.market = market.lower()
        self.api_key = api_key
        self.secret_key = secret_key
