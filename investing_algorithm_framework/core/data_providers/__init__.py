from typing import Dict, Any
from abc import ABC
from .data_provider import AbstractDataProvider
from investing_algorithm_framework.core.workers import Worker, \
    ScheduledWorker, RelationalWorker


class DataProvider(AbstractDataProvider, Worker, ABC):

    def work(self, **kwargs: Dict[str, Any]) -> None:
        self.provide_data()


class ScheduledDataProvider(AbstractDataProvider, ScheduledWorker, ABC):

    def work(self, **kwargs: Dict[str, Any]) -> None:
        self.provide_data()


class RelationalDataProvider(AbstractDataProvider, RelationalWorker, ABC):

    def work(self, **kwargs: Dict[str, Any]) -> None:
        self.provide_data()


__all__ = [
    'DataProvider',
    'ScheduledDataProvider',
    'RelationalDataProvider',
    'AbstractDataProvider'
]
