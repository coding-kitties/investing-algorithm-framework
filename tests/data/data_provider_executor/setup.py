import time
import numpy as np
from pandas import DataFrame
from wrapt import synchronized

from bot.data import DataProvider
from bot.events.observer import Observer
from bot.events.observable import Observable


def random_numpy_data_frame():
    return DataFrame(np.random.randint(1000, size=10000), columns=['p/e'])


class DummyDataProvider(DataProvider):

    def start(self):
        super().start()

    def provide_data(self) -> DataFrame:
        time.sleep(3)
        return random_numpy_data_frame()

    def add_observer(self, observer: Observer) -> None:
        super().add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super().remove_observer(observer)

    def clean_up(self):
        super(DummyDataProvider, self).clean_up()

    def get_id(self) -> str:
        return self.__class__.__name__


class SynchronizedDummyObserver(Observer):

    def __init__(self):
        self._update_count = 0

    @synchronized
    def update(self, observable, **kwargs) -> None:
        self._update_count += 1

    @property
    def get_update_count(self):
        return self._update_count


class DummyObserver(Observer):

    def __init__(self):
        self._update_count = 0

    def update(self, observable: Observable, **kwargs) -> None:
        self._update_count += 1

    @property
    def update_count(self):
        return self._update_count
