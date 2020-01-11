from typing import List

from bot.workers import Worker
from bot.data import DataProvider
from bot.executors import Executor
from bot.constants import DEFAULT_MAX_WORKERS


class DataProviderExecutor(Executor):

    def __init__(self, data_providers: List[DataProvider] = None, max_workers: int = DEFAULT_MAX_WORKERS):

        if max_workers:
            super(DataProviderExecutor, self).__init__(max_workers=max_workers)
        else:
            super(DataProviderExecutor, self).__init__()

        self._registered_data_providers: List[DataProvider] = []

        if data_providers is not None:
            self._registered_data_providers = data_providers

    def create_workers(self) -> List[Worker]:
        return self._registered_data_providers

    @property
    def registered_data_providers(self) -> List[DataProvider]:
        return self._registered_data_providers
