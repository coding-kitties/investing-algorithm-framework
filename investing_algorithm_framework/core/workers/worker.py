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

    id = None
    last_run: datetime = None

    def __init__(self):
        super(Worker, self).__init__()

    def start(self, *args, **kwargs) -> None:
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
            self.work(*args, **kwargs)
            self.notify_observers()
            self.update_last_run()
        except Exception as e:
            logger.error("Error occurred in worker {}".format(self.get_id()))
            logger.exception(e)
            self.update_last_run()

        logger.info("Worker {} finished".format(self.get_id()))

    @abstractmethod
    def work(self, *args, **kwargs) -> None:
        """
        Function that needs to be implemented by a concrete class.
        """
        pass

    def add_observer(self, observer: Observer) -> None:
        super(Worker, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(Worker, self).remove_observer(observer)

    def get_id(self) -> str:
        assert getattr(self, 'id', None) is not None, (
            "{} should either include a id attribute, or override the "
            "`get_id()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'id')

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
