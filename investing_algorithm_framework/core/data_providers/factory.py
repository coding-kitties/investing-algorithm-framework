from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.data_providers.binance_data_provider \
    import BinanceDataProvider


class DefaultDataProviderFactory:

    @staticmethod
    def of_identifier(identifier):
        if identifier.upper() == BINANCE:
            return BinanceDataProvider()

        return None
