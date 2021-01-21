from abc import abstractmethod, ABC

from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.core.exceptions import OperationalException


class AbstractPortfolioManager(ABC):

    def __init__(self, broker: str):
        self._broker = broker

    @property
    def broker(self):
        return self._broker

    @abstractmethod
    def get_portfolio_size(self, algorithm_context: AlgorithmContext) -> float:
        raise NotImplementedError()

    @abstractmethod
    def get_free_portfolio_size(self, algorithm_context: AlgorithmContext) \
            -> float:
        raise NotImplementedError()

    @abstractmethod
    def get_allocated_portfolio_size(
            self, algorithm_context: AlgorithmContext
    ) -> float:
        raise NotImplementedError()

    @abstractmethod
    def get_allocated_asset_size(
            self, asset, algorithm_context: AlgorithmContext
    ) -> float:
        raise NotImplementedError()

    def order_executed_notification(
            self,
            asset: str,
            max_price: float,
            quantity: int,
            commission: float,
            **kwargs
    ):
        raise OperationalException("Order executed not implemented")
