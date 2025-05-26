from typing import List

from tqdm import tqdm

from investing_algorithm_framework.domain import MarketService, \
    BacktestMarketDataSource, BACKTESTING_END_DATE, BACKTESTING_START_DATE, \
    BACKTESTING_INDEX_DATETIME, OperationalException, OHLCVMarketDataSource, \
    TickerMarketDataSource, OrderBookMarketDataSource, MarketDataType, \
    TimeFrame
from investing_algorithm_framework.services.configuration_service import \
    ConfigurationService
from investing_algorithm_framework.services.market_credential_service \
    import MarketCredentialService
from .market_data_source_service import MarketDataSourceService


class BacktestMarketDataSourceService(MarketDataSourceService):
    """
    BacktestMarketDataSourceService is a subclass of MarketDataSourceService.
    It is used to create market data sources for backtesting.

    In the constructor, it takes a list of BacktestMarketDataSource objects.
    These objects are used to prepare the data for backtesting.

    The prepare_data method of BacktestMarketDataSource is called in the
    constructor.

    The main difference between MarketDataSourceService and
    the BacktestMarketDataSourceService is that it will
    prepare the data for backtesting in the constructor.
    """
    def __init__(
        self,
        market_service: MarketService,
        market_credential_service: MarketCredentialService,
        configuration_service: ConfigurationService,
        market_data_sources: List[BacktestMarketDataSource] = None
    ):
        super().__init__(
            market_service=market_service,
            market_data_sources=None,
            market_credential_service=market_credential_service,
            configuration_service=configuration_service
        )
        self.market_data_sources = []

        # Add all market data sources to the list
        if market_data_sources is not None:
            for market_data_source in market_data_sources:
                self.add(market_data_source)

    def initialize_market_data_sources(self):
        config = self._configuration_service.get_config()
        backtest_start_date = config[BACKTESTING_START_DATE]
        backtest_end_date = config[BACKTESTING_END_DATE]
        backtest_market_data_sources = [
            market_data_source.to_backtest_market_data_source() for
            market_data_source in self._market_data_sources
        ]

        # Filter out the None values
        backtest_market_data_sources = [
            market_data_source for market_data_source in
            backtest_market_data_sources if market_data_source is not None
        ]

        for backtest_market_data_source in tqdm(
            backtest_market_data_sources,
            total=len(self._market_data_sources),
            desc="Preparing backtest market data",
            colour="GREEN"
        ):
            backtest_market_data_source.market_credential_service = \
                self._market_credential_service
            backtest_market_data_source.prepare_data(
                config=config,
                backtest_start_date=backtest_start_date,
                backtest_end_date=backtest_end_date
            )

        self.clear_market_data_sources()
        self.market_data_sources = backtest_market_data_sources

    def get_data(self, identifier):
        """
        This method is used to get the data for backtesting. It loops
        over all the backtest market data sources and returns the data
        for the given identifier (If there is a match).

        If there is no match, it raises an OperationalException.

        Args:
            identifier: The identifier of the market data source

        Returns:
            The data for the given identifier
        """
        config = self._configuration_service.get_config()
        backtest_index_date = config[BACKTESTING_INDEX_DATETIME]

        for market_data_source in self._market_data_sources:

            if market_data_source.get_identifier() == identifier:
                config = self._configuration_service.get_config()
                backtest_index_date = config[BACKTESTING_INDEX_DATETIME]
                data = market_data_source.get_data(
                    date=backtest_index_date, config=config
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
                    time_frame = TimeFrame.from_value(
                        market_data_source.time_frame
                    )
                    result["time_frame"] = time_frame.value
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
            f"Backtest market data source not found for {identifier}"
        )

    def get_ticker(self, symbol, market=None):
        ticker_market_data_source = self.get_ticker_market_data_source(
            symbol=symbol, market=market
        )

        if ticker_market_data_source is None:
            raise OperationalException(
                f"Backtest ticker data source "
                f"not found for {symbol} and market {market}"
            )

        config = self._configuration_service.get_config()
        backtest_index_date = config[BACKTESTING_INDEX_DATETIME]
        return ticker_market_data_source.get_data(
            date=backtest_index_date, config=config
        )

    def get_order_book(self, symbol, market):
        market_data_source = self.get_order_book_market_data_source(
            symbol=symbol, market=market
        )
        market_data_source.market_credential_service = \
            self._market_credential_service
        config = self._configuration_service.get_config()
        backtest_index_date = config[BACKTESTING_INDEX_DATETIME]
        return market_data_source.get_data(
            date=backtest_index_date, config=config
        )

    def get_ohlcv(
        self,
        symbol,
        from_timestamp,
        time_frame=None,
        market=None,
        to_timestamp=None
    ):
        market_data_source = self.get_ohlcv_market_data_source(
            symbol=symbol, market=market, time_frame=time_frame
        )
        market_data_source.market_credential_service = \
            self._market_credential_service
        config = self._configuration_service.get_config()
        backtest_index_date = config[BACKTESTING_INDEX_DATETIME]
        return market_data_source.get_data(
            date=backtest_index_date, config=config
        )

    def is_ohlcv_data_source_present(self, symbol, time_frame, market):
        market_data_source = self.get_ohlcv_market_data_source(
            symbol=symbol, market=market, time_frame=time_frame
        )
        return market_data_source is not None

    def add(self, market_data_source):

        if market_data_source is None:
            return

        # Check if there is already a market data source with the same
        # identifier
        for existing_market_data_source in self._market_data_sources:
            if existing_market_data_source.get_identifier() == \
                    market_data_source.get_identifier():
                return

        self._market_data_sources.append(market_data_source)
