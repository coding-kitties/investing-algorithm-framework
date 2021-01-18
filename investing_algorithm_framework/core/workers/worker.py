import logging
from random import randint
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
    last_run: datetime = None

    def start(self, **kwargs) -> None:
        """
        Function that will start the worker, and notify its observers when
        it is finished
        """

        try:
            logger.info("Starting worker {}".format(self.get_id()))
        except Exception as e:
            logger.exception(e)
            return

        try:
            self.work(**kwargs)
            self.notify_observers()
            self.update_last_run()
        except Exception as e:
            logger.error("Error occurred in worker {}".format(self.get_id()))
            logger.exception(e)
            self.update_last_run()

        logger.info("Worker {} finished".format(self.get_id()))

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

    @classmethod
    @synchronized
    def update_last_run(cls) -> None:
        """
        Update last run, this function is synchronized, which means that
        different instances can update the last_run attribute from different
        threads.
        """
        cls.last_run = datetime.now()

    @classmethod
    def get_last_run(cls):
        return cls.last_run
