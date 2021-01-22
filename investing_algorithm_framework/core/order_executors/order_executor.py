from abc import abstractmethod, ABC

from investing_algorithm_framework.core.context import AlgorithmContext


class AbstractOrderExecutor(ABC):

    def __init__(self, broker: str):
        self._broker = broker

    @property
    def broker(self):
        return self._broker

    @abstractmethod
    def execute_limit_order(
            self,
            asset: str,
            max_price: float,
            quantity: int,
            algorithm_context: AlgorithmContext,
            **kwargs
    ):
        raise NotImplementedError()
