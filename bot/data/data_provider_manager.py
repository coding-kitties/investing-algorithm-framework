import logging
from wrapt import synchronized
from queue import Queue
from typing import List, Dict

from bot.events.observer import Observer
from bot.events.observable import Observable
from bot.data.data_providers import DataProvider, DataProviderException
from bot.utils import StoppableThread

logger = logging.getLogger(__name__)


class DataProviderManager(Observable, Observer):
    """
    DataProviderManager handles all data providers, it spawns for every worker a new thread.
    """

    def __init__(self, data_providers: List[DataProvider] = None, max_workers: int = 2) -> None:
        super(DataProviderManager, self).__init__()

        self._max_workers = max_workers
        self._running_jobs: Dict[DataProvider, StoppableThread] = {}
        self._pending_data_providers = Queue()

        self._registered_data_providers: List[DataProvider] = []

        if data_providers is not None:

            # Add self as an observer
            for data_provider in data_providers:
                data_provider.add_observer(self)

            self._registered_data_providers = data_providers

    def _clean_up(self) -> None:
        self._running_jobs = []
        self._pending_data_providers = Queue()

    @property
    def registered_data_providers(self) -> List[DataProvider]:
        return self._registered_data_providers

    def start_data_providers(self) -> None:
        [self._pending_data_providers.put(data_provider) for data_provider in self.registered_data_providers]
        self._run_jobs()

    def stop_data_providers(self) -> None:

        for key in self._running_jobs:
            job = self._running_jobs[key]
            job.kill()
            job.join()

        self._clean_up()

    def _run_jobs(self) -> None:
        worker_iteration = self._max_workers - len(self._running_jobs)

        while worker_iteration > 0 and not self._pending_data_providers.empty():
            data_provider = self._pending_data_providers.get()
            job = StoppableThread(target=data_provider.start)
            self._running_jobs[data_provider] = job
            job.start()
            worker_iteration -= 1

    @property
    def running_workers(self) -> List[StoppableThread]:
        return [self._running_jobs[key] for key in self._running_jobs]

    def add_observer(self, observer: Observer) -> None:
        super(DataProviderManager, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(DataProviderManager, self).remove_observer(observer)

    @synchronized
    def update(self, observable, **kwargs) -> None:

        # remove worker from running jobs
        if isinstance(observable, DataProvider):
            del self._running_jobs[observable]

        if len(self.running_workers) == 0 and self._pending_data_providers.empty():
            self.notify_observers()
        else:
            self._run_jobs()


# Decorator to initialize with config
class ConfigDataProviderManager(DataProviderManager):

    def __init__(self, config: Dict[str, any]):

        data_providers: List[DataProvider] = []

        # Enable fmp data provider
        if config.get('data_providers', {}).get('fmp', {}).get('enabled', False):
            logger.info('Enabling data_provider.fmp ...')

            try:
                logging.info("Initializing FMP data provider")
                from bot.data.data_providers.fmp_data_provider import FMPDataProvider
                self.registered_data_providers.append(FMPDataProvider())
            except Exception as e:
                raise DataProviderException(str(e))

        super(ConfigDataProviderManager, self).__init__(data_providers)