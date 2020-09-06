from abc import ABC
from .data_provider import AbstractDataProvider
from investing_algorithm_framework.core.workers import Worker, \
    ScheduledWorker, RelationalWorker


class DataProvider(AbstractDataProvider, Worker, ABC):

    def work(self, *args, **kwargs) -> None:

        assert kwargs['algorithm_context'] is not None, {
            'Data provider must be started with a AlgorithmContext, make '
            'sure that you run the data provider in an AlgorithmContext '
            'instance.'
        }

        # Extract algorithm context argument
        algorithm_context = kwargs['algorithm_context']
        self.provide_data(algorithm_context)


class ScheduledDataProvider(AbstractDataProvider, ScheduledWorker, ABC):

    def work(self, *args, **kwargs) -> None:

        assert kwargs['algorithm_context'] is not None, {
            'Data provider must be started with a AlgorithmContext, make '
            'sure that you run the data provider in an AlgorithmContext '
            'instance.'
        }

        # Extract algorithm context argument
        algorithm_context = kwargs['algorithm_context']
        self.provide_data(algorithm_context)


class RelationalDataProvider(AbstractDataProvider, RelationalWorker, ABC):

    def work(self, *args, **kwargs) -> None:

        assert kwargs['algorithm_context'] is not None, {
            'Data provider must be started with a AlgorithmContext, make '
            'sure that you run the data provider in an AlgorithmContext '
            'instance.'
        }

        # Extract algorithm context argument
        algorithm_context = kwargs['algorithm_context']
        self.provide_data(algorithm_context)


__all__ = [
    'DataProvider',
    'ScheduledDataProvider',
    'RelationalDataProvider',
    'AbstractDataProvider'
]
