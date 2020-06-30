from typing import Dict, Any
from abc import abstractmethod, ABC

from investing_algorithm_framework.core.workers import ScheduledWorker, \
    Worker, RelationalWorker


class DataProviderInterface:
    """
    Class DataProviderInterface: interface for data provider implementation,
    this interface can be used to implement a data provider. A client then
    knows which method to call when presented with a 'data provider'
    """
    @abstractmethod
    def provide_data(self) -> None:
        pass


class DataProvider(DataProviderInterface, Worker, ABC):
    """
    Class DataProvider: makes use of the abstract Worker class and inherits the
    interface of of the DataProviderInterface.

    This is a Worker instance.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:

        # Call DataProviderInterface
        self.provide_data()


class ScheduledDataProvider(DataProviderInterface, ScheduledWorker, ABC):
    """
    Class ScheduledDataProvider: makes use of the abstract ScheduledWorker
    class and inherits the interface of of the DataProviderInterface.

    This is a ScheduledWorker instance, and therefore you must set the
    'time_unit' class attribute and the 'time_interval' class attribute.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:

        # Call DataProviderInterface
        self.provide_data()


class RelationalDataProvider(RelationalWorker, DataProviderInterface, ABC):
    """
    Class RelationalDataProvider: makes use of the abstract RelationalWorker
    class and inherits the interface of of the DataProviderInterface.

    This is a RelationalWorker instance, and therefore you must link it to
    another worker instance, by setting the 'run_after' class attribute.
    """

    def work(self, **kwargs: Dict[str, Any]) -> None:

        # Call DataProviderInterface
        self.provide_data()
