from investing_algorithm_framework.core.models.data_provider import \
    OrderBook, Ticker
from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.exceptions import OperationalException


class DataProvider(Identifier):

    def provide_raw_data(self, algorithm_context, **kwargs) -> dict:
        raise OperationalException(
            f"Data provider {self.__class__.__name__} does not support "
            f"trading data type raw data, please specify a supported "
            f"trading data type."
        )

    def provide_ticker(
            self, target_symbol, trading_symbol, algorithm_context, **kwargs
    ) -> Ticker:
        raise OperationalException(
            f"Data provider {self.__class__.__name__} does not support "
            f"trading data type ticker, please specify a supported "
            f"trading data type."
        )

    def provide_order_book(
            self, target_symbol, trading_symbol, algorithm_context, **kwargs
    ) -> OrderBook:
        raise OperationalException(
            f"Data provider {self.__class__.__name__} does not support "
            f"trading data type order book, please specify a supported "
            f"trading data type."
        )
