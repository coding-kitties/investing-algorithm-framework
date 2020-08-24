from typing import Dict, Any
from abc import ABC
from .data_provider import AbstractDataProvider
from investing_algorithm_framework.core.workers import Worker, \
    ScheduledWorker, RelationalWorker


class DataProvider(AbstractDataProvider, Worker, ABC):

    def work(self, **kwargs) -> None:

        assert kwargs['algorithm_context'] is not None, {
            'Data provider must be started with a AlgorithmContext, make '
            'sure that you run the data provider in an AlgorithmContext '
            'instance.'
        }

        self.provide_data(**kwargs)


class ScheduledDataProvider(AbstractDataProvider, ScheduledWorker, ABC):

    def work(self, **kwargs: Dict[str, Any]) -> None:

        assert kwargs['algorithm_context'] is not None, {
            'Data provider must be started with a AlgorithmContext, make '
            'sure that you run the data provider in an AlgorithmContext '
            'instance.'
        }

        self.provide_data(**kwargs)


class RelationalDataProvider(AbstractDataProvider, RelationalWorker, ABC):

    def work(self, **kwargs: Dict[str, Any]) -> None:

        assert kwargs['algorithm_context'] is not None, {
            'Data provider must be started with a AlgorithmContext, make '
            'sure that you run the data provider in an AlgorithmContext '
            'instance.'
        }

        self.provide_data(**kwargs)


__all__ = [
    'DataProvider',
    'ScheduledDataProvider',
    'RelationalDataProvider',
    'AbstractDataProvider'
]
