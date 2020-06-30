from typing import List
from abc import ABC
from concurrent.futures import ThreadPoolExecutor

from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.core.events.observer import Observer
from investing_algorithm_framework.core.events.observable import Observable
from investing_algorithm_framework.configuration.config_constants import \
    DEFAULT_MAX_WORKERS


class Executor(Observable, ABC):
    """
    Executor class: functions as a thread executor that will handle the
    executions of workers in asynchronous order.

    It will make use of the concurrent library for execution of the workers.
    Also the executor functions as an observable instance.
    """

    def __init__(
            self,
            workers: List[Worker],
            max_concurrent_workers: int = DEFAULT_MAX_WORKERS
    ) -> None:
        super(Executor, self).__init__()

        self._workers = workers
        self._max_concurrent_workers = max_concurrent_workers

    def start(self) -> None:
        """
        Main entry for the executor. The executor creates a ThreadPoolExecutor
        with the given amount of max_workers.

        It will then pass all the workers to the ThreadPoolExecutor. When
        finished it will update all its observers
        """

        with ThreadPoolExecutor(max_workers=self._max_concurrent_workers) as \
                executor:

            for worker in self.workers:
                executor.submit(worker.start)

        self.notify_observers()

    def add_observer(self, observer: Observer) -> None:
        super(Executor, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(Executor, self).remove_observer(observer)

    @property
    def workers(self) -> List[Worker]:
        return self._workers
