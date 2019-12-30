from queue import Queue
from typing import List, Dict

from bot.strategy.strategy import ObservableStrategy
from bot.events.observable import Observable
from bot.events.observer import Observer
from bot.utils import StoppableThread
from bot.constants import DEFAULT_MAX_WORKERS


class StrategyManager(Observable, Observer):

    def __init__(self, strategies: List[ObservableStrategy] = None, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        super(StrategyManager, self).__init__()

        self._max_workers = max_workers
        self._running_jobs: Dict[ObservableStrategy, StoppableThread] = {}
        self._pending_strategies = Queue()
        self._registered_strategies: List[ObservableStrategy] = []

        if strategies is not None:

            # Add self as an observer
            for strategy in strategies:
                strategy.add_observer(self)

            self._registered_strategies = strategies

    def _run_jobs(self) -> None:
        worker_iteration = self._max_workers - len(self._running_jobs)

        while worker_iteration > 0 and not self._pending_strategies.empty():
            data_provider = self._pending_strategies.get()
            job = StoppableThread(target=data_provider.start)
            self._running_jobs[data_provider] = job
            job.start()
            worker_iteration -= 1

    def add_observer(self, observer: Observer) -> None:
        super(StrategyManager, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(StrategyManager, self).remove_observer(observer)

    def update(self, observable, **kwargs) -> None:

        # remove worker from running jobs
        if isinstance(observable, ObservableStrategy):
            del self._running_jobs[observable]

        if len(self.running_workers) == 0 and self._pending_strategies.empty():
            self.notify_observers()
        else:
            self._run_jobs()

    @property
    def running_workers(self) -> List[StoppableThread]:
        return [self._running_jobs[key] for key in self._running_jobs]

    @property
    def processing(self) -> bool:
        return len(self._running_jobs) > 0 or not self._pending_strategies.empty()