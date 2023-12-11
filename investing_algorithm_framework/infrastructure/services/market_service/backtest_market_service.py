import logging
from datetime import datetime

from investing_algorithm_framework.domain import \
    BACKTESTING_INDEX_DATETIME, OperationalException, OHLCVMarketDataSource, \
    TickerMarketDataSource, OrderBookMarketDataSource
from .market_service import MarketService

logger = logging.getLogger("investing_algorithm_framework")


class BacktestMarketService(MarketService):

    def __init__(self, backtest_market_data_sources, configuration_service):
        self._backtest_market_data_sources = backtest_market_data_sources
        self._configuration_service = configuration_service
        self._data_index = {}
        self._unallocated = 0
        self._trading_symbol = None

    def initialize(self, portfolio_configuration):
        self._market = portfolio_configuration.market
        self._unallocated = portfolio_configuration.max_unallocated
        self._trading_symbol = portfolio_configuration.trading_symbol

    @property
    def backtest_market_data_sources(self):
        return self._backtest_market_data_sources

    @backtest_market_data_sources.setter
    def backtest_market_data_sources(self, backtest_market_data_sources):
        self._backtest_market_data_sources = backtest_market_data_sources

    def pair_exists(self, target_symbol: str, trading_symbol: str):
        pass

    def get_tickers(self, symbols):
        tickers = []

        for symbol in symbols:
            tickers.append(self.get_ticker(symbol))

        return tickers

    def get_order_book(self, symbol):

        for market_data_source in self._backtest_market_data_sources:
            if isinstance(market_data_source, OrderBookMarketDataSource):
                if market_data_source.symbol == symbol:
                    return market_data_source.get_data(
                        backtest_index_date=self._configuration_service[
                            BACKTESTING_INDEX_DATETIME
                        ]
                    )

        raise OperationalException(
            f"No order book backtest data found for symbol: {symbol}"
        )

    def get_order_books(self, symbols):
        order_books = []

        for symbol in symbols:
            order_books.append(self.get_order_book(symbol))

        return order_books

    def get_balance(self):
        return {self._trading_symbol: {"free": self._unallocated}}

    def get_prices(self, symbols):
        return self.get_tickers(symbols)

    def get_ohlcvs(
        self, symbols, time_frame, from_timestamp, to_timestamp=None
    ):
        ohlcvs = {}

        for symbol in symbols:

            try:
                ohlcvs[symbol] = self.get_ohlcv(
                    symbol, time_frame, from_timestamp, to_timestamp
                )
            except Exception as e:
                logger.exception(e)
                logger.error(f"Could not retrieve ohlcv data for {symbol}")

        return ohlcvs

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

    def cancel_order(self, order_id):
        pass

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

        for market_data_source in self._backtest_market_data_sources:
            if isinstance(market_data_source, OHLCVMarketDataSource):
                if market_data_source.symbol == symbol \
                        and market_data_source.timeframe == time_frame:
                    return market_data_source.get_data(
                        backtest_index_date=self._configuration_service[
                            BACKTESTING_INDEX_DATETIME
                        ]
                    )

        raise OperationalException(
            f"No ohlcv backtest data found for symbol: {symbol}"
        )

    def get_ticker(self, symbol):
        for market_data_source in self._backtest_market_data_sources:
            if isinstance(market_data_source, TickerMarketDataSource):
                if market_data_source.symbol == symbol:
                    return market_data_source.get_data(
                        backtest_index_date=self._configuration_service.config[
                            BACKTESTING_INDEX_DATETIME
                        ]
                    )

        raise OperationalException(
            f"No ohlcv backtest data found for symbol: {symbol}"
        )
