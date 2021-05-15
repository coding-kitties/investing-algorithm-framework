from abc import abstractmethod, ABC

from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.core.exceptions import OperationalException


class AbstractPortfolioManager(ABC):
    broker = None

    def __init__(self, broker: str = None):

        if self.broker is None:
            self.broker = broker

        # If ID is none generate a new unique ID
        if self.broker is None:
            raise OperationalException(
                "Portfolio manager has no broker specified"
            )

    def get_broker(self) -> str:
        assert getattr(self, 'broker', None) is not None, (
            "{} should either include a broker attribute, or override the "
            "`get_broker()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'broker')

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

    @abstractmethod
    def get_price(
            self,
            fiat_currency: str,
            symbol: str,
            algorithm_context: AlgorithmContext
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
