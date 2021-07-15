from abc import abstractmethod, ABC

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Order


class OrderExecutor(ABC):
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
    def execute_limit_order(
            self,
            to_be_traded_symbol: str,
            traded_against_symbol: str,
            price: float,
            amount: float,
            algorithm_context,
            **kwargs
    ) -> bool:
        raise NotImplementedError()

    def validate_order_execution(self, order: Order):

        if not order.completed:
            return self.is_order_executed(
                order.first_symbol,
                order.second_symbol,
                order.price,
                order.amount
            )

        return True

    @abstractmethod
    def is_order_executed(
            self,
            to_be_traded_symbol: str,
            traded_against_symbol: str,
            price: float,
            amount: float
    ) -> bool:
        raise NotImplementedError()
