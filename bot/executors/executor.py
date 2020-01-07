import logging
from queue import Queue
from typing import List, Dict
from wrapt import synchronized
from abc import abstractmethod, ABC

from bot.workers import Worker
from bot import OperationalException
from bot.utils import StoppableThread
from bot.events.observer import Observer
from bot.events.observable import Observable
from bot.constants import DEFAULT_MAX_WORKERS

logger = logging.getLogger(__name__)


class Executor(Observable):
    """
    Executor class: functions as an abstract class that will handle the executions of workers.
    """

    def __init__(self):
        super(Executor, self).__init__()

        self._pending_workers: Queue = None

    def start(self) -> None:
        self._initialize()
        self.run_jobs()

    @abstractmethod
    def run_jobs(self) -> None:
        pass

    def _initialize(self):
        workers = self.create_workers()

        if not workers or len(workers) == 0:
            raise OperationalException("There where no workers initialized for the executor instance")

        self._pending_workers = Queue()

        for worker in workers:
            self._pending_workers.put(worker)

    @abstractmethod
    def stop_running_worker(self, worker: Worker) -> None:
        pass

    def clean_up(self):
        self._pending_workers = None

    def stop(self) -> None:
        self.clean_up()

    @abstractmethod
    def create_workers(self) -> List[Worker]:
        pass

    @property
    def pending_workers(self) -> Queue:
        return self._pending_workers

    def add_observer(self, observer: Observer) -> None:
        super(Executor, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(Executor, self).remove_observer(observer)

    @property
    def processing(self) -> bool:

        if self._pending_workers is not None:
            return not self.pending_workers.empty()

        return False


class AsynchronousExecutor(Executor, Observer, ABC):
    """
    AsynchronousExecutor class: functions as an abstract class that will handle the executions of workers in synchronous order
    """

    def __init__(self,  max_workers: int = DEFAULT_MAX_WORKERS):
        super(AsynchronousExecutor, self).__init__()

        self._max_workers = max_workers
        self._running_workers: List[Worker] = []
        self._running_threads: Dict[Worker, StoppableThread] = {}

    def run_jobs(self) -> None:

        worker_iteration = self._max_workers - len(self._running_workers)

        while worker_iteration > 0 and not self._pending_workers.empty():
            worker = self._pending_workers.get()
            worker_iteration -= 1
            thread = StoppableThread(target=worker.start)
            worker.add_observer(self)
            thread.start()
            self._running_threads[worker] = thread
            self._running_workers.append(worker)

    @synchronized
    def update(self, observable, **kwargs) -> None:

        if observable in self._running_workers:
            self._running_workers.remove(observable)

        if not self.processing:
            self.notify_observers()
        else:
            self.run_jobs()

    def stop_running_worker(self, worker: Worker) -> None:
        """
        With only synchronous workers you can't stop a function,
        you need to wait til the current worker is finished
        """
        self._pending_workers = Queue()

    @property
    def processing(self) -> bool:
        return super(AsynchronousExecutor, self).processing \
               or (self._running_workers is not None and len(self._running_workers) > 0)


class SynchronousExecutor(Executor, ABC):
    """
    SingleExecutor class: functions as an abstract class that will handle the executions of workers in synchronous order
    """

    def __init__(self):
        # Can at most have 1 worker running
        super(SynchronousExecutor, self).__init__()

    def run_jobs(self) -> None:

        while not self._pending_workers.empty():
            worker = self._pending_workers.get()
            worker.start()

        # Let everybody know that we are finished
        self.notify_observers()

    def stop_running_worker(self, worker: Worker) -> None:
        """
        With only synchronous workers you can't stop a function,
        you need to wait til the current worker is finished
        """
        self._pending_workers = Queue()
