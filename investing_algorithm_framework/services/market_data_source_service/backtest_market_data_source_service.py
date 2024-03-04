from typing import List
from tqdm import tqdm

from investing_algorithm_framework.domain import MarketService, \
    BacktestMarketDataSource, BACKTESTING_END_DATE, BACKTESTING_START_DATE, \
    BACKTESTING_INDEX_DATETIME, OperationalException
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
    """
    def __init__(
        self,
        market_data_sources: List[BacktestMarketDataSource],
        market_service: MarketService,
        market_credential_service: MarketCredentialService,
        configuration_service: ConfigurationService,
    ):
        super().__init__(
            market_service=market_service,
            market_data_sources=None,
            market_credential_service=market_credential_service,
        )
        self._market_data_sources: List[BacktestMarketDataSource] \
            = market_data_sources
        self._configuration_service: ConfigurationService = \
            configuration_service

        for backtest_market_data_source in tqdm(
            market_data_sources,
            total=len(self._market_data_sources),
            desc="Preparing backtest market data",
            colour="GREEN"
        ):

            if backtest_market_data_source is not None:
                backtest_market_data_source.market_credentials_service = \
                    self._market_credential_service
                backtest_market_data_source.prepare_data(
                    config=configuration_service.get_config(),
                    backtest_start_date=configuration_service
                    .get_config()[BACKTESTING_START_DATE],
                    backtest_end_date=configuration_service
                    .get_config()[BACKTESTING_END_DATE],
                    market_credential_service=self._market_credential_service
                )

    def get_data(self, identifier):
        """
        This method is used to get the data for backtesting. It loops
        over all the backtest market data sources and returns the data
        for the given identifier (If there is a match).
        """
        for backtest_market_data_source in self._market_data_sources:
            if backtest_market_data_source.identifier == identifier:
                backtest_market_data_source.market_credentials_service = \
                    self._market_credential_service
                return backtest_market_data_source.get_data(
                    backtest_index_date=self._configuration_service
                    .config[BACKTESTING_INDEX_DATETIME],
                )

        raise OperationalException(
            f"Backtest market data source not found for {identifier}"
        )

    def get_ticker(self, symbol, market):
        market_data_source = self.get_ticker_market_data_source(
            symbol=symbol, market=market
        )

        if market_data_source is None:
            raise OperationalException(
                f"Backtest ticker data source "
                f"not found for {symbol} and market {market}"
            )

        market_data_source.market_credentials_service = \
            self._market_credential_service
        return market_data_source.get_data(
            backtest_index_date=self._configuration_service
            .config[BACKTESTING_INDEX_DATETIME],
        )

    def get_order_book(self, symbol, market):
        market_data_source = self.get_order_book_market_data_source(
            symbol=symbol, market=market
        )
        market_data_source.market_credential_service = \
            self._market_credential_service
        return market_data_source.get_data(
            backtest_index_date=self._configuration_service
            .config[BACKTESTING_INDEX_DATETIME],
        )

    def get_ohlcv(
        self, symbol, from_timestamp, market, time_frame, to_timestamp=None
    ):
        market_data_source = self.get_ohlcv_market_data_source(
            symbol=symbol, market=market, time_frame=time_frame
        )
        market_data_source.market_credential_service = \
            self._market_credential_service
        return market_data_source.get_data(
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            backtest_index_date=self._configuration_service
            .config[BACKTESTING_INDEX_DATETIME],
        )

    def is_ohlcv_data_source_present(self, symbol, time_frame, market):
        market_data_source = self.get_ohlcv_market_data_source(
            symbol=symbol, market=market, time_frame=time_frame
        )
        return market_data_source is not None
