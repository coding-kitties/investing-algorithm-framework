import logging
from typing import Dict, Any
from abc import abstractmethod

from investing_algorithm_framework.core.workers import ScheduledWorker

logger = logging.getLogger(__name__)


class DataProviderException(Exception):
    """
    Should be raised when an data_provider related error occurs, for
    example if an authorization for an API fails,
    i.e.: raise DataProviderException('Provided api token is false')
    """

    def __init__(self, message: str) -> None:
        super().__init__(self)
        self.message = message

    def __str__(self) -> str:
        return self.message


class DataProvider(ScheduledWorker):
    """
    Class DataProvider: An entity which responsibility is to provide data
    from an external source. Where a data_providers source is defined as
    any third party service that provides data e.g  cloud storage,
    REST API, or website.

    A data_provider must always be run with the start function from it´s
    super class. Otherwise depended
    observers will not be updated.
    """

    @abstractmethod
    def provide_data(self) -> None:
        pass

    def work(self, **kwargs: Dict[str, Any]) -> None:
        logger.info("Starting data provider {}".format(self.get_id()))
        self.provide_data()
