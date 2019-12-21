from bot.events.observable import Observable
from bot.events.observer import Observer

import pytest


class DummyObserver(Observer):
    updated = False

    def update(self, observable: Observable, **kwargs) -> None:
        updates = True


class DummyObservable(Observable):

    def add_observer(self, observer: Observer) -> None:
        super().add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super().remove_observer(observer)


def test_add_observer():

    observer_one = DummyObserver()
    observer_two = DummyObserver()

    observable = Observable()
    observable.add_observer(observer_one)
    observable.add_observer(observer_two)

    assert len(observable.observers) == 2


