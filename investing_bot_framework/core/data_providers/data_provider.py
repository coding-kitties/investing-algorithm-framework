from typing import Dict, Any
from abc import abstractmethod

from investing_bot_framework.core.workers import Worker
from investing_bot_framework.core.utils import TimeUnit


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
    Class DataProvider: An entity which responsibility is to provide data_providers from an external data_providers
    source. Where a data_providers source is defined as any third party service that provides data_providers,
    e.g  cloud storage, REST API, or website.

    A data_providers provider must always be run with the start function from it´s super class. Otherwise depend
    observers will not be updated.
    """

    def get_time_unit(self) -> TimeUnit:
        assert getattr(self, 'time_unit', None) is not None, (
            "{} should either include a time_unit attribute, or override the "
            "`get_time_unit()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'time_unit')

    def get_time_interval(self) -> int:
        assert getattr(self, 'time_interval', None) is not None, (
            "{} should either include a time_interval attribute, or override the "
            "`get_time_interval()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'time_interval')

    @abstractmethod
    def provide_data(self) -> None:
        pass

    def work(self, **kwargs: Dict[str, Any]) -> None:
        self.provide_data()


