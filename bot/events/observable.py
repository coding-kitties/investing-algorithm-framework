from typing import List
from abc import ABC, abstractmethod
from bot.events.observer import Observer


class Observable(ABC):

    def __init__(self):
        self._observers: List[Observer] = []

    @abstractmethod
    def add_observer(self, observer: Observer) -> None:

        if not self._observers:
            self._observers = []

        if isinstance(observer, Observer) and observer not in self._observers:
            self._observers.append(observer)

    @abstractmethod
    def remove_observer(self, observer: Observer) -> None:

        if not self._observers:
            return

        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, **kwargs) -> None:

        for observer in self._observers:
            observer.update(self, **kwargs)

    @property
    def observers(self) -> List[Observer]:
        return self._observers
