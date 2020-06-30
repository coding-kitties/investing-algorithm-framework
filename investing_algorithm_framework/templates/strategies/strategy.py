from typing import Dict, Any
from abc import abstractmethod, ABC

from investing_algorithm_framework.core.workers import ScheduledWorker, \
    Worker, RelationalWorker


class StrategyInterface(ABC):
    """
    Interface for strategy implementation, this interface can be used
    to implement a strategy. A client then knows which method to call
    when presented with a 'strategy'
    """

    @abstractmethod
    def apply_strategy(self) -> None:
        pass


class Strategy(Worker, StrategyInterface, ABC):
    """
    Strategy that makes use of the abstract Worker class and inherits the
    interface of of the StrategyInterface.

    This is a Worker instance.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:

        # Call StrategyInterface
        self.apply_strategy()


class RelationalStrategy(RelationalWorker, StrategyInterface, ABC):
    """
    RelationalStrategy that makes use of the abstract RelationalWorker class
    and inherits the interface of the StrategyInterface.

    This is a RelationalWorker instance, and therefore you must link it to
    another worker instance, by setting the 'run_after' class attribute.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:

        # Call StrategyInterface
        self.apply_strategy()


class ScheduledStrategy(ScheduledWorker, StrategyInterface, ABC):
    """
    Class ScheduledStrategy that makes use of the abstract ScheduledWorker
    class and inherits the interface of the StrategyInterface.

    This is a ScheduledWorker instance, and therefore you must set the
    'time_unit' class attribute and the 'time_interval' class attribute.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:

        # Call StrategyInterface
        self.apply_strategy()
