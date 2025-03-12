import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict

from polars import DataFrame

logger = logging.getLogger("investing_algorithm_framework")


class MarketService(ABC):

    def __init__(self, market_credential_service):
        self._market_credential_service = market_credential_service
        self._config = None

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    @abstractmethod
    def pair_exists(
        self,
        market,
        target_symbol: str,
        trading_symbol: str,
    ):
        raise NotImplementedError()

    @abstractmethod
    def get_ticker(self, symbol, market):
        raise NotImplementedError()

    @abstractmethod
    def get_tickers(self, symbols, market):
        raise NotImplementedError()

    @abstractmethod
    def get_order_book(self, symbol, market):
        raise NotImplementedError()

    @abstractmethod
    def get_order_books(self, symbols, market):
        raise NotImplementedError()

    @abstractmethod
    def get_order(self, order, market):
        raise NotImplementedError()

    @abstractmethod
    def get_orders(self, symbol, market, since: datetime = None):
        raise NotImplementedError()

    @abstractmethod
    def get_balance(self, market) -> Dict[str, float]:
        raise NotImplementedError()

    @abstractmethod
    def create_limit_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float,
        market
    ):
        raise NotImplementedError()

    @abstractmethod
    def create_limit_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float,
        market
    ):
        raise NotImplementedError()

    @abstractmethod
    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        market
    ):
        raise NotImplementedError()

    @abstractmethod
    def cancel_order(self, order, market):
        raise NotImplementedError()

    @abstractmethod
    def get_open_orders(
        self, market, target_symbol: str = None, trading_symbol: str = None
    ):
        raise NotImplementedError()

    @abstractmethod
    def get_closed_orders(
        self, market, target_symbol: str = None, trading_symbol: str = None
    ):
        raise NotImplementedError()

    @abstractmethod
    def get_ohlcv(
        self, symbol, time_frame, from_timestamp, market, to_timestamp=None
    ) -> DataFrame:
        raise NotImplementedError()

    @abstractmethod
    def get_ohlcvs(
        self, symbols, time_frame, from_timestamp, market, to_timestamp=None
    ) -> Dict[str, DataFrame]:
        raise NotImplementedError()

    @property
    def market_credentials(self):

        if self._market_credential_service is None:
            return []

        return self._market_credential_service.get_all()

    def get_market_credentials(self):
        return self._market_credential_service.get_all()

    def get_market_credential(self, market):

        if self.market_credentials is None:
            return None

        if market is None:
            return None

        for market_data_credentials in self.market_credentials:

            if market_data_credentials.market.upper() == market.upper():
                return market_data_credentials

        return None

    @abstractmethod
    def get_symbols(self, market):
        """
        Get all available symbols for a market
        """
        raise NotImplementedError()
