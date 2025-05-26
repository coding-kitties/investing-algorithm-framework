from datetime import datetime
from random import randint

from investing_algorithm_framework.services import MarketDataSourceService


class RandomPriceMarketDataSourceServiceStub(MarketDataSourceService):

    def get_ticker(self, symbol, market=None):
        return {
            "symbol": symbol,
            "ask": randint(1, 100),
            "bid": randint(1, 100),
            "last": randint(1, 100),
            "volume": randint(1, 100),
            "timestamp": datetime.utcnow()
        }

class MarketDataSourceServiceStub(MarketDataSourceService):

    def __init__(
        self,
        market_service,
        market_credential_service,
        configuration_service,
        market_data_sources
    ):
        super().__init__(
            market_service,
            market_credential_service,
            configuration_service,
            market_data_sources
        )

    def initialize_market_data_sources(self):
        pass

    def get_ticker(self, symbol, market=None):
        return {
            "symbol": symbol,
            "ask": randint(1, 100),
            "bid": randint(1, 100),
            "last": randint(1, 100),
            "volume": randint(1, 100),
            "timestamp": datetime.utcnow()
        }
