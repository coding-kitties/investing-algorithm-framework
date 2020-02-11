from typing import Dict, Any
from abc import abstractmethod, ABC

from investing_bot_framework.core.workers import Worker
from investing_bot_framework.core.data.data_providers.mixins import RestApiClientMixin


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


class DataProvider(Worker):
    """
    Class DataProvider: An entity which responsibility is to provide data from an external data source. Where a data
    source is defined as any third party service that provides data, e.g  cloud storage, REST API, or website.

    A data provider must always be run with the start function from it´s super class. Otherwise depend observers will
    not be updated.
    """

    def __init__(self):
        super(DataProvider, self).__init__()
        self._data: Any = None

    @abstractmethod
    def provide_data(self, **kwargs: Dict[str, Any]) -> Any:
        pass

    def work(self, **kwargs: Dict[str, Any]) -> None:
        self._data = self.provide_data()

    @property
    def data(self) -> Any:

        if self._data is None:
            raise DataProviderException("Could not provide data, data is not set by {}".format(self.get_id()))

        return self._data

    def clean_up(self) -> None:
        self._data = None


class RestApiDataProvider(RestApiClientMixin, DataProvider, ABC):
    pass
