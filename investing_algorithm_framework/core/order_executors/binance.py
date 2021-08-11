from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.order_executors import OrderExecutor
from investing_algorithm_framework.core.mixins import BinanceOrderExecutorMixin


class BinanceOrderExecutor(BinanceOrderExecutorMixin, OrderExecutor):
    identifier = BINANCE

    def __init__(self, identifier: str = None):
        super(BinanceOrderExecutor, self).__init__(identifier)

        if identifier is not None:
            self.identifier = identifier

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
        super(BinanceOrderExecutor, self).initialize(algorithm_context)
