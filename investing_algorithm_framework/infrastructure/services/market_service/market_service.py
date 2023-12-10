import logging
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger("investing_algorithm_framework")


class MarketService(ABC):
    _market = None

    @property
    def market(self):
        return self._market

    @market.setter
    def market(self, value):
        self._market = value

    @abstractmethod
    def initialize(self, portfolio_configuration):
        pass

    @abstractmethod
    def pair_exists(self, target_symbol: str, trading_symbol: str):
        pass

    @abstractmethod
    def get_ticker(self, symbol):
        pass

    @abstractmethod
    def get_tickers(self, symbols):
        pass

    @abstractmethod
    def get_order_book(self, symbol):
        pass

    @abstractmethod
    def get_order_books(self, symbols):
        pass

    @abstractmethod
    def get_order(self, order):
        pass

    @abstractmethod
    def get_orders(self, symbol, since: datetime = None):
        pass

    @abstractmethod
    def get_balance(self):
        pass

    @abstractmethod
    def create_limit_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        pass

    @abstractmethod
    def create_limit_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        pass

    @abstractmethod
    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
    ):
        pass

    @abstractmethod
    def cancel_order(self, order):
        pass

    @abstractmethod
    def get_open_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        pass

    @abstractmethod
    def get_closed_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        pass

    @abstractmethod
    def get_prices(self, symbols):
        pass

    @abstractmethod
    def get_ohlcv(self, symbol, time_frame, from_timestamp, to_timestamp=None):
        pass

    @abstractmethod
    def get_ohlcvs(
        self, symbols, time_frame, from_timestamp, to_timestamp=None
    ):
        pass
