import logging
from typing import Dict, Any
from pandas import DataFrame
from abc import abstractmethod

from bot.workers import Worker

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

    def __str__(self) -> str:
        return self.message

    def __json__(self):
        return {
            'msg': self.message
        }


class DataProvider(Worker):

    def __init__(self):
        super(DataProvider, self).__init__()

        self._data: DataFrame = None

    @abstractmethod
    def provide_data(self, **kwargs: Dict[str, Any]) -> DataFrame:
        pass

    def work(self, **kwargs: Dict[str, Any]) -> None:
        self._data = self.provide_data()

    @property
    def data(self) -> DataFrame:

        if self._data is None:
            raise DataProviderException("Could not provide data, data is not set")
        else:
            data = self._data
            self.clean_up()
            return data

    def clean_up(self) -> None:
        self._data = None

    def get_id(self) -> str:
        return self.__class__.__name__
