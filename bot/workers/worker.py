from abc import abstractmethod, ABC
from typing import Dict, Any

from bot.events.observable import Observable
from bot.events.observer import Observer


class Worker(Observable, ABC):

    def start(self, **kwargs: Dict[str, Any]) -> None:
        self.work(**kwargs)
        self.notify_observers()

    @abstractmethod
    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass

    def add_observer(self, observer: Observer) -> None:
        super(Worker, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(Worker, self).remove_observer(observer)

    @abstractmethod
    def get_id(self) -> str:
        pass
