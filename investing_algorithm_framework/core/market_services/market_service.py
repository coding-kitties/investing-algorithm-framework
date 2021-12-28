from abc import ABC, abstractmethod
from investing_algorithm_framework.core.market_identifier \
    import MarketIdentifier
from investing_algorithm_framework.core.models import TimeInterval


class MarketService(ABC, MarketIdentifier):

    @abstractmethod
    def pair_exists(self, target_symbol: str, trading_symbol: str):
        pass

    def get_price(self, target_symbol: str, trading_symbol: str):
        return self.get_ticker(target_symbol, trading_symbol)

    @abstractmethod
    def get_prices(
        self,
        target_symbol: str,
        trading_symbol: str,
        interval: TimeInterval
    ):
        pass

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
