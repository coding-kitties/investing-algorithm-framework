from typing import List
from datetime import datetime, timezone

from investing_algorithm_framework.domain import MarketService, \
    MarketDataSource, OHLCVMarketDataSource, TickerMarketDataSource, \
    OrderBookMarketDataSource, TimeFrame, OperationalException, \
    MarketDataType
from investing_algorithm_framework.services.configuration_service import \
    ConfigurationService
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

    Attributes:
        - market_service: MarketService
            The market service that is used to get the data from the market
        - market_credential_service: MarketCredentialService
            The market credential service that is used to get the credentials
            for the market
        - configuration_service: ConfigurationService
            The configuration service that is used to get the configuration
            for the algorithm
        - _market_data_sources: List[MarketDataSource]
            The list of market data sources that are used by the algorithm
    """
    _market_data_sources: List[MarketDataSource] = []

    def __init__(
        self,
        market_service: MarketService,
        market_credential_service: MarketCredentialService,
        configuration_service: ConfigurationService,
        market_data_sources: List[MarketDataSource] = None
    ):

        if market_data_sources is not None:
            self._market_data_sources: List[MarketDataSource] \
                = market_data_sources

        self._market_service: MarketService = market_service
        self._market_credential_service: MarketCredentialService = \
            market_credential_service
        self._configuration_service = configuration_service

    def initialize_market_data_sources(self):

        for market_data_source in self._market_data_sources:
            market_data_source.market_credential_service = \
                self._market_credential_service

    def get_ticker(self, symbol, market=None):
        ticker_market_data_source = self.get_ticker_market_data_source(
            symbol=symbol, market=market
        )
        config = self._configuration_service.get_config()
        date = config.get("DATE_TIME", None)

        if ticker_market_data_source is not None:

            if date is not None:
                return ticker_market_data_source.get_data(
                   end_date=date, config=config
                )

            return ticker_market_data_source.get_data(
                end_date=datetime.now(tz=timezone.utc), config=config
            )

        return self._market_service.get_ticker(symbol, market)

    def get_order_book(self, symbol, market=None):
        order_book_market_data_source = self.get_order_book_market_data_source(
            symbol=symbol, market=market
        )
        config = self._configuration_service.get_config()

        if order_book_market_data_source is not None:
            return order_book_market_data_source.get_data(
                end_date=datetime.now(tz=timezone.utc), config=config
            )

        return self._market_service.get_order_book(symbol, market)

    def get_ohlcv(
        self,
        symbol,
        from_timestamp,
        time_frame,
        market=None,
        to_timestamp=None
    ):
        ohlcv_market_data_source = self.get_ohlcv_market_data_source(
            symbol=symbol, market=market, time_frame=time_frame
        )
        config = self._configuration_service.get_config()

        if ohlcv_market_data_source is not None:
            return ohlcv_market_data_source.get_data(
                end_date=datetime.now(tz=timezone.utc), config=config
            )

        return self._market_service.get_ohlcv(
            symbol=symbol,
            time_frame=time_frame,
            from_timestamp=from_timestamp,
            market=market,
            to_timestamp=to_timestamp
        )

    def get_data_for_strategy(self, strategy):
        """
        Function to get the data for the strategy. It loops over all
          the market data sources in the strategy and returns the
          data for each

        Args:
            strategy: The strategy for which the data is required

        Returns:
            The data for the strategy in dictionary format with
              the keys being the identifier of the market data sources
        """
        identifiers = []
        if strategy.market_data_sources is not None:
            for market_data_source in strategy.market_data_sources:

                if isinstance(market_data_source, MarketDataSource):
                    identifiers.append(market_data_source.get_identifier())
                elif isinstance(market_data_source, str):
                    identifiers.append(market_data_source)
                else:
                    raise OperationalException(
                        "Market data source must be a string " +
                        "or MarketDataSource"
                    )

        market_data = {"metadata": {
            MarketDataType.OHLCV: {},
            MarketDataType.TICKER: {},
            MarketDataType.ORDER_BOOK: {},
            MarketDataType.CUSTOM: {}
        }}

        for identifier in identifiers:
            result_data = self.get_data(identifier)

            if "symbol" in result_data and result_data["symbol"] is not None \
                    and "type" in result_data \
                        and result_data["type"] is not None:
                type = result_data["type"]
                symbol = result_data["symbol"]
                time_frame = result_data["time_frame"]

                if symbol not in market_data["metadata"][type]:
                    market_data["metadata"][type][symbol] = {}

                if time_frame is None:
                    market_data["metadata"][type][symbol] = identifier

            if time_frame is not None and \
                time_frame not in \
                    market_data["metadata"][type][symbol]:
                market_data["metadata"][type][symbol][time_frame] = identifier

            market_data[identifier] = result_data["data"]
        return market_data

    def get_data(self, identifier):
        for market_data_source in self._market_data_sources:

            if market_data_source.get_identifier() == identifier:
                config = self._configuration_service.get_config()
                date = config.get("DATE_TIME", None)

                if date is not None:
                    data = market_data_source.get_data(
                        end_date=date, config=config
                    )
                elif "DATE_TIME" in config:
                    data = market_data_source.get_data(
                        end_date=config["DATE_TIME"], config=config,
                    )
                else:
                    data = market_data_source.get_data(
                        end_date=datetime.now(tz=timezone.utc), config=config,
                    )

                result = {
                    "data": data,
                    "type": None,
                    "symbol": None,
                    "time_frame": None
                }

                # Add metadata to the data
                if isinstance(market_data_source, OHLCVMarketDataSource):
                    result["type"] = MarketDataType.OHLCV
                    time_frame = market_data_source.time_frame

                    if time_frame is not None:
                        time_frame = TimeFrame.from_value(time_frame)
                        result["time_frame"] = time_frame.value
                    else:
                        result["time_frame"] = TimeFrame.CURRENT.value

                    result["symbol"] = market_data_source.symbol
                    return result

                if isinstance(market_data_source, TickerMarketDataSource):
                    result["type"] = MarketDataType.TICKER
                    result["time_frame"] = TimeFrame.CURRENT
                    result["symbol"] = market_data_source.symbol
                    return result

                if isinstance(market_data_source, OrderBookMarketDataSource):
                    result["type"] = MarketDataType.ORDER_BOOK
                    result["time_frame"] = TimeFrame.CURRENT
                    result["symbol"] = market_data_source.symbol
                    return result

                result["type"] = MarketDataType.CUSTOM
                result["time_frame"] = TimeFrame.CURRENT
                result["symbol"] = market_data_source.symbol
                return result

        raise OperationalException(
            f"Market data source not found for {identifier}"
        )

    def get_ticker_market_data_source(self, symbol, market=None):

        if self.market_data_sources is not None:
            for market_data_source in self._market_data_sources:
                if isinstance(market_data_source, TickerMarketDataSource):
                    if market is not None:
                        if market_data_source.market.upper() == market.upper()\
                                and market_data_source.symbol.upper() \
                                == symbol.upper():
                            return market_data_source
                    else:
                        if market_data_source.symbol.upper() \
                                == symbol.upper():
                            return market_data_source

        return None

    def get_ohlcv_market_data_source(
        self, symbol, time_frame=None, market=None
    ):
        """
        Function to get the OHLCV market data source for a symbol,
          time frame and market.

        Parameters:
            symbol: str - The symbol of the asset
            time_frame: TimeFrame - The time frame of the data
            market: str - The market of the asset

        Returns:
            OHLCVMarketDataSource - The OHLCV market data source for the
            symbol, time frame and market
        """
        if time_frame is not None:
            time_frame = TimeFrame.from_value(time_frame)

        if self.market_data_sources is not None:

            for market_data_source in self._market_data_sources:
                if isinstance(market_data_source, OHLCVMarketDataSource):

                    if market is not None and time_frame is not None:
                        if market_data_source.market.upper() == market.upper()\
                                and market_data_source.symbol.upper() \
                                == symbol.upper() and \
                                time_frame.equals(
                                    market_data_source.time_frame
                                ):
                            return market_data_source
                    elif market is not None:
                        if market_data_source.market.upper() == market.upper()\
                                and market_data_source.symbol.upper() \
                                == symbol.upper():
                            return market_data_source
                    elif time_frame is not None:
                        if market_data_source.symbol.upper() \
                                == symbol.upper() and \
                                time_frame.equals(
                                    market_data_source.time_frame
                                ):
                            return market_data_source
                    else:
                        if market_data_source.symbol.upper() \
                                == symbol.upper():
                            return market_data_source

        return None

    def get_order_book_market_data_source(self, symbol, market=None):

        if self.market_data_sources is not None:
            for market_data_source in self._market_data_sources:
                if isinstance(market_data_source, OrderBookMarketDataSource):

                    if market is not None:
                        if market_data_source.market.upper() == market.upper()\
                                and market_data_source.symbol.upper() \
                                == symbol.upper():
                            return market_data_source
                    else:
                        if market_data_source.symbol.upper() \
                                == symbol.upper():
                            return market_data_source

        return None

    @property
    def market_data_sources(self):
        return self._market_data_sources

    @market_data_sources.setter
    def market_data_sources(self, market_data_sources):

        for market_data_source in market_data_sources:
            self.add(market_data_source)

    def clear_market_data_sources(self):
        """
        Function to clear the market data sources
        """
        self._market_data_sources = []

    def add(self, market_data_source):

        # Check if the market data source is an instance of MarketDataSource
        if not isinstance(market_data_source, MarketDataSource):
            return

        # Check if there is already a market data source with the same
        # identifier
        for existing_market_data_source in self._market_data_sources:
            if existing_market_data_source.get_identifier() == \
                    market_data_source.get_identifier():
                return

        market_data_source.market_credential_service = \
            self._market_credential_service
        self._market_data_sources.append(market_data_source)

    def get_market_data_sources(self):
        return self._market_data_sources

    def has_ticker_market_data_source(self, symbol, market=None):
        return self.get_ticker_market_data_source(symbol, market) is not None
