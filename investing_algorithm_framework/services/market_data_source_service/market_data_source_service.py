from typing import List

from investing_algorithm_framework.domain import MarketService, \
    MarketDataSource, OHLCVMarketDataSource, TickerMarketDataSource, \
    OrderBookMarketDataSource
from investing_algorithm_framework.services.market_credential_service \
    import MarketCredentialService


class MarketDataSourceService:
    """
    This class is responsible for managing the market data sources.

    It is used by the algorithm to get market data from different sources.
    The MarketDataSourceService will first check if there is a market data
    source that matches the symbol, market and time frame provided by the user.
    If there is, it will use that market data source to get the data. If there
    is not, it will use the MarketService to get the data.
    """
    _market_data_sources: List[MarketDataSource] = []

    def __init__(
        self,
        market_service: MarketService,
        market_credential_service: MarketCredentialService,
        market_data_sources: List[MarketDataSource] = None,
    ):

        if market_data_sources is not None:
            self._market_data_sources: List[MarketDataSource] \
                = market_data_sources

        self._market_service: MarketService = market_service
        self._market_credential_service: MarketCredentialService = \
            market_credential_service

    def get_ticker(self, symbol, market=None):
        ticker_market_data_source = self.get_ticker_market_data_source(
            symbol=symbol, market=market
        )

        if ticker_market_data_source is not None:
            return ticker_market_data_source.get_data(
                market_credential_service=self._market_credential_service
            )
        return self._market_service.get_ticker(symbol, market)

    def get_order_book(self, symbol, market=None):
        order_book_market_data_source = self.get_order_book_market_data_source(
            symbol=symbol, market=market
        )

        if order_book_market_data_source is not None:
            return order_book_market_data_source.get_data(
                market_credential_service=self._market_credential_service
            )

        return self._market_service.get_order_book(symbol, market)

    def get_ohlcv(
        self,
        symbol,
        time_frame,
        from_timestamp,
        market=None,
        to_timestamp=None
    ):
        ohlcv_market_data_source = self.get_ohlcv_market_data_source(
            symbol=symbol, market=market, time_frame=time_frame
        )

        if ohlcv_market_data_source is not None:
            return ohlcv_market_data_source.get_data(
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                market_credential_service=self._market_credential_service
            )

        return self._market_service.get_ohlcv(
            symbol=symbol,
            time_frame=time_frame,
            from_timestamp=from_timestamp,
            market=market,
            to_timestamp=to_timestamp
        )

    def get_data(self, identifier):

        for market_data_source in self._market_data_sources:
            if market_data_source.get_identifier() == identifier:
                return market_data_source.get_data(
                    market_credential_service=self._market_credential_service
                )

    def get_ticker_market_data_source(self, symbol, market=None):

        if self.market_data_sources is not None:
            for market_data_source in self._market_data_sources:
                if isinstance(market_data_source, TickerMarketDataSource):

                    if market is not None:
                        if market_data_source.market.lower() == market.lower()\
                                and market_data_source.symbol.lower() \
                                == symbol.lower():
                            return market_data_source
                    else:
                        if market_data_source.symbol.lower() \
                                == symbol.lower():
                            return market_data_source

        return None

    def get_ohlcv_market_data_source(self, symbol, time_frame, market=None):

        if self.market_data_sources is not None:
            for market_data_source in self._market_data_sources:
                if isinstance(market_data_source, OHLCVMarketDataSource):

                    if market is not None:

                        if market_data_source.market.lower() == market.lower()\
                                and market_data_source.symbol.lower() \
                                == symbol.lower() and \
                                market_data_source.timeframe == time_frame:
                            return market_data_source
                    else:
                        if market_data_source.symbol.lower() \
                                == symbol.lower() and \
                                market_data_source.timeframe == time_frame:
                            return market_data_source

        return None

    def get_order_book_market_data_source(self, symbol, market=None):

        if self.market_data_sources is not None:
            for market_data_source in self._market_data_sources:
                if isinstance(market_data_source, OrderBookMarketDataSource):

                    if market is not None:
                        if market_data_source.market.lower() == market.lower()\
                                and market_data_source.symbol.lower() \
                                == symbol.lower():
                            return market_data_source
                    else:
                        if market_data_source.symbol.lower() \
                                == symbol.lower():
                            return market_data_source

        return None

    @property
    def market_data_sources(self):
        return self._market_data_sources

    @market_data_sources.setter
    def market_data_sources(self, market_data_sources):
        self._market_data_sources = market_data_sources

    def add(self, market_data_source):
        self._market_data_sources.append(market_data_source)

    def get_market_data_sources(self):
        return self._market_data_sources
