from typing import Dict, Any
from abc import ABC, abstractmethod
from investing_algorithm_framework.core.workers import Worker, \
    ScheduledWorker, RelationalWorker


class OrderExecutorInterface(ABC):
    """
    Interface for OrderExecutor implementation, this interface can be used
    to implement a OrderExecutor. A client then knows which method to call
    when presented with a 'OrderExecutor'
    """
    @abstractmethod
    def execute_orders(self) -> None:
        pass


class OrderExecutor(OrderExecutorInterface, Worker, ABC):
    """
    OrderExecutor that makes use of the abstract Worker class and inherits the
    interface of of the OrderExecutorInterface.

    This is a Worker instance.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:
        # Call OrderExecutorInterface
        self.execute_orders()


class RelationalOrderExecutor(OrderExecutorInterface, RelationalWorker, ABC):
    """
    RelationalOrderExecutor that makes use of the abstract RelationalWorker
    class and inherits the interface of the OrderExecutorInterface.

    This is a RelationalWorker instance, and therefore you must link it to
    another worker instance, by setting the 'run_after' class attribute.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:

        # Call OrderExecutorInterface
        self.execute_orders()


class ScheduledOrderExecutor(OrderExecutorInterface, ScheduledWorker, ABC):
    """
    Class ScheduledOrderExecutor that makes use of the abstract ScheduledWorker
    class and inherits the interface of the OrderExecutorInterface.

    This is a ScheduledWorker instance, and therefore you must set the
    'time_unit' class attribute and the 'time_interval' class attribute.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:

        # Call OrderExecutorInterface
        self.execute_orders()
