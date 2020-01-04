import logging
from typing import List, Tuple

from bot.utils import StoppableThread
from bot.executors import WorkerExecutor
from bot.events.observable import Observable
from bot.data.data_provider.data_provider import DataProvider

logger = logging.getLogger(__name__)


class DataProviderExecutor(WorkerExecutor):

    def __init__(self, data_providers: List[DataProvider] = None, max_workers: int = None) -> None:

        if max_workers:
            super(DataProviderExecutor, self).__init__(max_workers=max_workers)
        else:
            super(DataProviderExecutor, self).__init__()

        self._registered_data_providers: List[DataProvider] = []

        if data_providers is not None:
            self._registered_data_providers = data_providers

    def create_jobs(self) -> List[Tuple[Observable, StoppableThread]]:
        jobs: List[(Observable, StoppableThread)] = []

        for data_provider in self._registered_data_providers:
            jobs.append((data_provider, StoppableThread(target=data_provider.start)))

        return jobs

    def start(self) -> None:
        super(DataProviderExecutor, self).start()

    @property
    def registered_data_providers(self) -> List[DataProvider]:
        return self._registered_data_providers
