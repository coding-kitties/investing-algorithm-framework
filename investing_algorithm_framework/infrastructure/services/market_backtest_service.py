import logging
from datetime import datetime

from investing_algorithm_framework.domain import \
    TradingDataType, BACKTESTING_INDEX_DATETIME, \
    OperationalException, OHLCVMarketDataSource, TickerMarketDataSource
from .market_service import MarketService

logger = logging.getLogger("investing_algorithm_framework")


class MarketBacktestService(MarketService):

    def __init__(self, backtest_data_directory, configuration_service):
        self._backtest_data_directory = backtest_data_directory
        self._configuration_service = configuration_service
        self._backtest_market_data_sources = []
        self._data_index = {}

    def initialize(self, portfolio_configuration):
        self._market = portfolio_configuration.market

    @property
    def backtest_market_data_sources(self):
        return self._backtest_market_data_sources

    @backtest_market_data_sources.setter
    def backtest_market_data_sources(self, backtest_market_data_sources):
        self._backtest_market_data_sources = backtest_market_data_sources

    def index_data(self):
        self._data_index = {
            TradingDataType.OHLCV.value: {}, TradingDataType.TICKER.value: {}
        }

        for market_data_source in self._backtest_market_data_sources:
            if isinstance(market_data_source, TickerMarketDataSource):
                self._data_index[TradingDataType.TICKER.value]: {
                    market_data_source.symbol: market_data_source
                }

            if isinstance(market_data_source, OHLCVMarketDataSource):
                self._data_index[TradingDataType.OHLCV.value]\
                    [market_data_source.symbol] = market_data_source

    def get_order(self, order):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality get_order"
        )

    def get_orders(self, symbol, since: datetime = None):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality get_orders"
        )

    def create_limit_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality create_limit_buy_order"
        )

    def create_limit_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality create_limit_sell_order"
        )

    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality create_market_sell_order"
        )

    def cancel_order(self, order):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality cancel_order"
        )

    def get_open_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality get_open_orders"
        )

    def get_closed_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality get_closed_orders"
        )

    def get_ohlcv(self, symbol, time_frame, from_timestamp, to_timestamp=None):
        self.index_data()

        if symbol not in self._data_index[TradingDataType.OHLCV.value]:
            raise OperationalException(
                f"No ohlcv backtest data found for symbol: {symbol}"
            )

        market_data_source = self._data_index[
            TradingDataType.TICKER.value][symbol]

        return market_data_source.get_data(
            backtest_index_date=self._configuration_service[
                BACKTESTING_INDEX_DATETIME
            ]
        )

    def get_ticker(self, symbol):
        self.index_data()

        if symbol not in self._data_index[TradingDataType.TICKER.value]:

            if symbol in self._data_index[TradingDataType.OHLCV.value]:
                market_data_source = self._data_index[
                    TradingDataType.OHLCV.value][symbol]
                data = market_data_source.get_data(
                    backtest_index_date=self._configuration_service.config.get(
                        BACKTESTING_INDEX_DATETIME
                    )
                )
                return {
                    "symbol": symbol,
                    "bid": data[-1][4],
                    "ask": data[-1][4],
                    "datetime": data[-1][0],
                }
            else:
                raise OperationalException(
                    f"No ticker backtest data found for symbol: {symbol}"
                )
        else:
            market_data_source = self._data_index[
                TradingDataType.TICKER.value][symbol]

        return market_data_source.get_data(
            backtest_index_date=self._configuration_service[
                BACKTESTING_INDEX_DATETIME
            ]
        )
