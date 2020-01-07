from typing import List

from bot.workers import Worker
from bot.data import DataProvider
from bot.constants import DEFAULT_MAX_WORKERS
from bot.executors import AsynchronousExecutor, SynchronousExecutor


class AsyncDataProviderExecutor(AsynchronousExecutor):

    def __init__(self, data_providers: List[DataProvider] = None, max_workers: int = DEFAULT_MAX_WORKERS):

        if max_workers:
            super(AsyncDataProviderExecutor, self).__init__(max_workers=max_workers)
        else:
            super(AsyncDataProviderExecutor, self).__init__()

        self._registered_data_providers: List[DataProvider] = []

        if data_providers is not None:
            self._registered_data_providers = data_providers

    def create_workers(self) -> List[Worker]:
        return self._registered_data_providers

    @property
    def registered_data_providers(self) -> List[DataProvider]:
        return self._registered_data_providers


class SyncDataProviderExecutor(SynchronousExecutor):

    def __init__(self, data_providers: List[DataProvider] = None):
        super(SyncDataProviderExecutor, self).__init__()

        self._registered_data_providers: List[DataProvider] = []

        if data_providers is not None:
            self._registered_data_providers = data_providers

    def create_workers(self) -> List[Worker]:
        return self._registered_data_providers

    @property
    def registered_data_providers(self) -> List[DataProvider]:
        return self._registered_data_providers
