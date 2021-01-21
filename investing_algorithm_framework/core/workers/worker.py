import logging
from abc import abstractmethod, ABC
from wrapt import synchronized
from datetime import datetime

from investing_algorithm_framework.core.events.observable import Observable
from investing_algorithm_framework.core.events.observer import Observer
from investing_algorithm_framework.configuration.constants \
    import FRAMEWORK_NAME

logger = logging.getLogger(FRAMEWORK_NAME)


class Worker(Observable, ABC):
    """
    Class Worker: manages the execution of a task and the context around
    executing it.
    """

    def __init__(self):
        super().__init__()
        self._last_run: datetime = None

    @property
    def last_run(self):
        return self._last_run

    @last_run.setter
    def last_run(self, date_time):
        self._last_run = date_time

    def start(self, **kwargs) -> None:
        """
        Function that will start the worker, and notify its observers when
        it is finished
        """

        try:
            self.work(**kwargs)
            self.notify_observers()
            self.update_last_run()
        except Exception as e:
            logger.error("Error occurred in worker")
            logger.exception(e)
            self.update_last_run()

    @abstractmethod
    def work(self, **kwargs) -> None:
        """
        Function that needs to be implemented by a concrete class.
        """
        pass

    def add_observer(self, observer: Observer) -> None:
        super(Worker, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(Worker, self).remove_observer(observer)

    @synchronized
    def update_last_run(self) -> None:
        """
        Update last run, this function is synchronized, which means that
        different instances can update the last_run attribute from different
        threads.
        """

        self.last_run = datetime.now()
