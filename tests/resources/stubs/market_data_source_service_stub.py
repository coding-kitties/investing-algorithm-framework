from investing_algorithm_framework.services import MarketDataSourceService
from random import randint
from datetime import datetime


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
