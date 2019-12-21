from typing import List
from abc import ABC, abstractmethod
from bot.events.observer import Observer


class Observable(ABC):

    observers: List[Observer] = []

    @abstractmethod
    def add_observer(self, observer: Observer) -> None:

        if observer not in self.observers:
            self.observers.append(observer)

    @abstractmethod
    def remove_observer(self, observer: Observer) -> None:

        if observer in self.observers:
            self.observers.remove(observer)

    def notify_observers(self, **kwargs):

        for observer in self.observers:
            observer.update(self, **kwargs)
