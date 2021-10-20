from investing_algorithm_framework.core.mixins import BinanceDataProviderMixin
from investing_algorithm_framework.core.data_providers.data_provider import \
    DataProvider


class BinanceDataProvider(BinanceDataProviderMixin, DataProvider):
    pass
