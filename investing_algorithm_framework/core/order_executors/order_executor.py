from abc import abstractmethod, ABC

from investing_algorithm_framework.core.models import Order
from investing_algorithm_framework.core.identifier import Identifier


class OrderExecutor(ABC, Identifier):

    def initialize(self, algorithm_context):
        pass

    @abstractmethod
    def execute_limit_order(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def execute_market_order(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def update_order_status(
            self, order: Order, algorithm_context, **kwargs
    ) -> bool:
        raise NotImplementedError()
