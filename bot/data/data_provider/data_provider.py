import logging
from typing import Dict, Any
from pandas import DataFrame
from abc import abstractmethod

from bot.workers import Worker

logger = logging.getLogger(__name__)


class DataProviderException(Exception):
    """
    Should be raised when an data_provider related error occurs, for example if an authorization for an API fails,
    i.e.: raise DataProviderException('Provided api token is false')
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
    """
    Class DataProvider: An entity which responsibility is to provide data from an external data source. Where a data
    source is defined as any third party service that provides data, e.g  cloud storage, REST API, or website
    """

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
            raise DataProviderException("Could not provide data, data is not set by {}".format(self.get_id()))
        else:
            data = self._data
            self.clean_up()
            return data

    def clean_up(self) -> None:
        self._data = None


