from abc import ABC, abstractmethod
from typing import List
from investing_algorithm_framework.domain import Order


class OrderExecutorService(ABC):

    def __init__(self, market_data_sources):
        self._market_data_sources = market_data_sources

    @abstractmethod
    def execute_order(self, order: Order, portfolio_configuration) -> Order:
        pass

    @abstractmethod
    def retrieve_order(self, order_id: str, portfolio_configuration) -> Order:
        pass

    @abstractmethod
    def retrieve_orders(self, order_ids: List[str], portfolio_configuration) -> List[Order]:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str, portfolio_configuration) -> Order:
        pass

    @abstractmethod
    def cancel_orders(self, order_ids: List[str], portfolio_configuration) -> List[Order]:
        pass

    @abstractmethod
    def has_executed(self, order_id: str, portfolio_configuration) -> bool:
        pass
