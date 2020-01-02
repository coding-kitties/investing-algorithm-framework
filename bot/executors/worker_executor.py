from queue import Queue
from abc import abstractmethod
from wrapt import synchronized
from typing import Dict, List, Tuple, Any

from bot import OperationalException
from bot.utils import StoppableThread
from bot.events.observer import Observer
from bot.events.observable import Observable
from bot.constants import DEFAULT_MAX_WORKERS


class WorkerExecutor(Observable, Observer):
    """
    WorkerExecutor class: Abstract class that will schedule, execute and manage workers.
    """

    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        super(WorkerExecutor, self).__init__()
        self._max_workers = max_workers
        self._running_jobs: Dict[Observable, StoppableThread] = {}
        self._pending_jobs = Queue()

    def _initialize(self):
        jobs = self.create_jobs()

        if not jobs or len(jobs) == 0:
            raise OperationalException("There where no jobs initialized for the WorkerExecutor instance")

        for job in jobs:
            self._pending_jobs.put(job)

    def _run_jobs(self) -> None:
        """
        Function that will create a job and run it
        """

        worker_iteration = self._max_workers - len(self._running_jobs)

        while worker_iteration > 0 and not self._pending_jobs.empty():
            (observable, thread) = self._pending_jobs.get()
            observable.add_observer(self)
            self._running_jobs[observable] = thread
            thread.start()
            worker_iteration -= 1

    def start(self):
        self._initialize()
        self._run_jobs()

    def stop(self) -> None:

        for key in self._running_jobs:
            job = self._running_jobs[key]
            job.kill()
            job.join()

        self._clean_up()

    def _clean_up(self) -> None:
        self._running_jobs = []
        self._pending_jobs = Queue()

    @abstractmethod
    def create_jobs(self) -> List[Tuple[Observable, StoppableThread]]:
        """
        Function should return a instance of StoppableThread running on of the pending jobs in the queue.
        """
        pass

    def add_observer(self, observer: Observer) -> None:
        super(WorkerExecutor, self).add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super(WorkerExecutor, self).remove_observer(observer)

    @synchronized
    def update(self, observable, **kwargs) -> None:

        if observable in self._running_jobs:
            del self._running_jobs[observable]

        if not self.processing:
            self.notify_observers()
        else:
            self._run_jobs()

    @property
    def running_workers(self) -> List[StoppableThread]:
        return [self._running_jobs[key] for key in self._running_jobs]

    @property
    def processing(self) -> bool:
        return len(self._running_jobs) > 0 or not self._pending_jobs.empty()
