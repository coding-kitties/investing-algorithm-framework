import logging
from typing import List, Dict, Tuple

from bot.utils import StoppableThread
from bot.executors import WorkerExecutor
from bot.events.observable import Observable
from bot.data.data_provider.data_provider import DataProvider, DataProviderException

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

    @property
    def registered_data_providers(self) -> List[DataProvider]:
        return self._registered_data_providers


class ConfigDataProviderExecutor(DataProviderExecutor):

    def __init__(self, config: Dict[str, any], data_providers: List[DataProvider] = None):

        data_providers: List[DataProvider] = []

        # Enable fmp data provider
        if config.get('data_provider', {}).get('fmp', {}).get('enabled', False):
            logger.info('Enabling data_provider.fmp ...')

            try:
                logging.info("Initializing FMP data provider")
                from bot.data.data_provider.template.fmp_data_provider import FMPDataProvider
                data_providers.append(FMPDataProvider())
            except Exception as e:
                raise DataProviderException(str(e))

        if data_providers is not None:

            for data_provider in data_providers:
                data_providers.append(data_provider)

        super(ConfigDataProviderExecutor, self).__init__(data_providers)
