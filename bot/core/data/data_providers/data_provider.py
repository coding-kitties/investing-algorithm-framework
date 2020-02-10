from typing import Dict, Any
from abc import abstractmethod, ABC

from bot.core.workers import Worker
from bot.core.data.data_providers.mixins import RestApiClientMixin


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

    id = None

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

    def get_id(self) -> str:
        assert getattr(self, 'id', None) is not None, (
            "{} should either include a id attribute, or override the "
            "`get_id()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'id')


class RestApiDataProvider(RestApiClientMixin, DataProvider, ABC):
    pass
