from abc import ABC, abstractmethod


class ExchangeClient(ABC):

    @abstractmethod
    def get_ticker(self, target_symbol: str, trading_symbol: str):
        pass

    @abstractmethod
    def get_order_book(self, target_symbol: str, trading_symbol: str):
        pass

    @abstractmethod
    def get_balance(self, symbol: str = None):
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
    def create_market_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
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
    def get_orders(self, target_symbol: str, trading_symbol: str):
        pass

    @abstractmethod
    def get_order(self, order_id, target_symbol: str, trading_symbol: str):
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
    def cancel_order(self, order_id):
        pass