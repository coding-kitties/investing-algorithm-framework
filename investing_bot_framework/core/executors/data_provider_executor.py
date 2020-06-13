from typing import List

from investing_bot_framework.core.workers import Worker
from investing_bot_framework.core.data_providers import DataProvider
from investing_bot_framework.core.executors import Executor
from investing_bot_framework.core.configuration.config_constants import DEFAULT_MAX_WORKERS


class DataProviderExecutor(Executor):
    """
    Class DataProviderExecutor: is an executor for DataProvider instances.
    """

    def __init__(self, data_providers: List[DataProvider] = None, max_workers: int = DEFAULT_MAX_WORKERS):
        super(DataProviderExecutor, self).__init__(max_workers=max_workers)

        self._registered_data_providers: List[DataProvider] = []

        if data_providers is not None and len(data_providers) > 0:
            self._registered_data_providers = data_providers

    def create_workers(self) -> List[Worker]:
        return self._registered_data_providers

    @property
    def registered_data_providers(self) -> List[DataProvider]:
        return self._registered_data_providers

    @property
    def configured(self):
        return self._registered_data_providers is not None and len(self._registered_data_providers) > 0