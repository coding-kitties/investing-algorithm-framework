from abc import ABC, abstractmethod
from .algorithm_context import AlgorithmContext
from .algorithm_context_configuration import AlgorithmContextConfiguration


class AlgorithmContextInitializer(ABC):

    from investing_algorithm_framework.core.context.algorithm_context \
        import AlgorithmContext

    @abstractmethod
    def initialize(self, algorithm_context: AlgorithmContext) -> None:
        raise NotImplementedError()


__all__ = [
    'AlgorithmContext',
    'AlgorithmContextInitializer',
    'AlgorithmContextConfiguration'
]
