from abc import abstractmethod, ABC
from typing import Dict, Any

from investing_algorithm_framework.core.events.observable import Observable
from investing_algorithm_framework.core.events.observer import Observer


class Worker(Observable, ABC):
    """
    Class Worker: manages the execution of a task and the context around
    executing it.
    """

    id = None

    def start(self, **kwargs: Dict[str, Any]) -> None:
        """
        Function that will start the worker, and notify its observers when
        it is finished
        """

        self.work(**kwargs)
        self.notify_observers()

    @abstractmethod
    def work(self, **kwargs: Dict[str, Any]) -> None:
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
