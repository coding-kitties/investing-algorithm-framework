from abc import ABC, abstractmethod
from typing import List

from investing_algorithm_framework.core.events.observer import Observer


class Observable(ABC):
    """
    Class Observable: manages and updates it's observers.
    """

    def __init__(self) -> None:
        self._observers: List[Observer] = []

    @abstractmethod
    def add_observer(self, observer: Observer) -> None:

        if isinstance(observer, Observer) and observer not in self._observers:
            self._observers.append(observer)

    @abstractmethod
    def remove_observer(self, observer: Observer) -> None:

        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, **kwargs) -> None:

        for observer in self._observers:
            observer.update(self, **kwargs)

    @property
    def observers(self) -> List[Observer]:
        return self._observers
