from abc import ABC, abstractmethod

from investing_algorithm_framework.core.context.algorithm_context import \
    AlgorithmContext
from investing_algorithm_framework.core.context \
    .algorithm_context_configuration import AlgorithmContextConfiguration


class AlgorithmContextInitializer(ABC):

    from investing_algorithm_framework.core.context.algorithm_context \
        import AlgorithmContext

    @abstractmethod
    def initialize(self, algorithm: AlgorithmContext) -> None:
        raise NotImplementedError()


algorithm = AlgorithmContext()

__all__ = [
    'algorithm',
    'AlgorithmContext',
    'AlgorithmContextInitializer',
    'AlgorithmContextConfiguration'
]
