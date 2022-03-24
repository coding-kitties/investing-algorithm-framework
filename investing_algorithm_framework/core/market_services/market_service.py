from abc import ABC, abstractmethod


class MarketService(ABC):

    @abstractmethod
    def pair_exists(self, target_symbol: str, trading_symbol: str):
        pass

    @abstractmethod
    def get_prices(self, symbols):
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
    def get_orders(self, symbol: str, since=None):
        pass

    @abstractmethod
    def get_order(self, order_id):
        pass

    @abstractmethod
    def get_closed_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    @abstractmethod
    def get_ohclv(self, symbol, time_unit, since):
        pass

    @abstractmethod
    def get_ohclvs(self, symbols, time_unit, since):
        pass
