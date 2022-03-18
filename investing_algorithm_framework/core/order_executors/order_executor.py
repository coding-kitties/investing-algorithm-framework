from abc import abstractmethod, ABC

from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.models import Order


class OrderExecutor(ABC, Identifier):

    def initialize(self, algorithm_context, throw_exception=True):
        pass

    @abstractmethod
    def execute_order(
        self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        raise NotImplementedError()

    @abstractmethod
    def check_order_status(
        self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        raise NotImplementedError()
