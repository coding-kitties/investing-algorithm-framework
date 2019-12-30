import logging
from abc import ABC, abstractmethod
from pandas import DataFrame

from bot.events.observable import Observable
from bot.events.observer import Observer

logger = logging.getLogger(__name__)


class DataProviderException(Exception):
    """
    Should be raised with a data_provider-formatted message in an _data_provider_* method
    if ticker is wrong, i.e.:
    raise DataProviderException('*Status:* `ticker is not valid`')
    """
    def __init__(self, message: str) -> None:
        super().__init__(self)
        self.message = message

    def __str__(self):
        return self.message

    def __json__(self):
        return {
            'msg': self.message
        }


class DataProvider(Observable):

    def __init__(self):
        super(DataProvider, self).__init__()
        self._data: DataFrame = None

    def start(self):
        self._data = self.provide_data()
        self.notify_observers()

    def add_observer(self, observer: Observer) -> None:
        super().add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super().remove_observer(observer)

    @abstractmethod
    def provide_data(self) -> DataFrame:
        pass

    @property
    def data(self):

        if self._data is None:

            raise DataProviderException("Could not provide data")

        else:
            return self._data

    def clear(self):
        self._data = None

    @abstractmethod
    def get_id(self) -> str:
        pass