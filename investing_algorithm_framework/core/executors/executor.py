from queue import Queue
from typing import List, Dict
from wrapt import synchronized
from abc import abstractmethod, ABC

from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.utils import StoppableThread
from investing_algorithm_framework.core.events.observer import Observer
from investing_algorithm_framework.core.events.observable import Observable
from investing_algorithm_framework.configuration.config_constants import \
    DEFAULT_MAX_WORKERS


class Executor(Observable, Observer, ABC):
    """
    Executor class: functions as an abstract class that will handle the
    executions of workers in asynchronous order.
    """

    def __init__(self,  max_workers: int = DEFAULT_MAX_WORKERS):
        super(Executor, self).__init__()

        self._max_workers = max_workers
        self._pending_workers: Queue = None
        self._running_threads: Dict[Worker, StoppableThread] = {}

    def start(self) -> None:
        """
        Main entry for the executor.
        """

        self._initialize()
        self.run_jobs()

    def stop(self) -> None:
        """
        Function that will stop all running workers.
        """

        for worker in self._running_threads:
            self.stop_running_worker(worker)

        self.clean_up()

    def clean_up(self):
        """
        Clean ups the resources.
        """

        self._pending_workers: Queue = None
        self._running_threads: Dict[Worker, StoppableThread] = {}

    def _initialize(self):
        """
        Functions that initializes the pending workers.
        """

        workers = self.create_workers()

        if not workers or len(workers) == 0:
            raise OperationalException("There where no workers initialized "
                                       "for the executor instance")

        self._pending_workers = Queue()

        for worker in workers:
            self._pending_workers.put(worker)

    @abstractmethod
    def create_workers(self) -> List[Worker]:
        """
        Abstract function that will create the workers.
        """
        pass

    def run_jobs(self) -> None:
        """
        Function that will start all the workers.
        """

        worker_iteration = self._max_workers - len(
            self._running_threads.keys()
        )

        while worker_iteration > 0 and not self._pending_workers.empty():
            worker = self._pending_workers.get()
            worker_iteration -= 1
            thread = StoppableThread(target=worker.start)
            worker.add_observer(self)
            self._running_threads[worker] = thread
            thread.start()

    @synchronized
    def update(self, observable, **kwargs) -> None:
        """
        Observer implementation.
        """

        if observable in self._running_threads:
            del self._running_threads[observable]

        if not self.processing:
            self.notify_observers()
        else:
            self.run_jobs()

    def stop_running_worker(self, worker: Worker) -> None:
        """
        Function that will stop a running worker.
        """

        thread = self._running_threads[worker]
        thread.kill()

    def add_observer(self, observer: Observer) -> None:
        super(Executor, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(Executor, self).remove_observer(observer)

    @property
    def processing(self) -> bool:
        """
        Property that will show if the executor is running.
        """

        return (self._pending_workers is not None
                and not self._pending_workers.empty()) or \
               (self._running_threads is not None
                and len(self._running_threads.keys()) > 0)
