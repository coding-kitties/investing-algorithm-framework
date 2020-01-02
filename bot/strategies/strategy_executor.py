from typing import List, Tuple

from bot import OperationalException
from bot.executors import WorkerExecutor
from bot.events.observable import Observable
from bot.strategies import ObservableStrategy
from bot.utils import StoppableThread, DataSource


class StrategyExecutor(WorkerExecutor):

    def __init__(self, strategies: List[ObservableStrategy] = None):
        super(StrategyExecutor, self).__init__()

        self._registered_strategies: List[ObservableStrategy] = []

        self._data_sources: List[DataSource] = []

        if strategies is not None:
            self._registered_strategies = strategies

    @property
    def data_sources(self) -> List[DataSource]:
        return self.data_sources

    @data_sources.setter
    def data_sources(self, data_sources: List[DataSource]) -> None:
        self._data_sources = data_sources

    def start(self):

        if self.data_sources is None:
            raise OperationalException("Can't run strategies without data sources")

        super(StrategyExecutor, self).start()

    def create_jobs(self) -> List[Tuple[Observable, StoppableThread]]:
        jobs: List[Tuple[Observable, StoppableThread]] = []

        for strategy in self.registered_strategies:
            jobs.append((strategy, StoppableThread(target=strategy.start, kwargs={"data_sources": self.data_sources})))

        return jobs

    @property
    def registered_strategies(self) -> List[ObservableStrategy]:
        return self._registered_strategies
