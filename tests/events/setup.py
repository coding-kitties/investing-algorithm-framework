from time import sleep
from wrapt import synchronized

from bot.events.observable import Observable
from bot.events.observer import Observer


class DummyObserver(Observer):

    def __init__(self):
        self._update_count = 0

    def update(self, observable: Observable, **kwargs) -> None:
        self._update_count += 1

    @property
    def update_count(self):
        return self._update_count


class SynchronizedDummyObserver(Observer):

    def __init__(self):
        self._update_count = 0

    @synchronized
    def update(self, observable: Observable, **kwargs) -> None:
        self._update_count += 1

    @property
    def update_count(self):
        return self._update_count


class DummyObservable(Observable):

    def add_observer(self, observer: Observer) -> None:
        super().add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super().remove_observer(observer)
