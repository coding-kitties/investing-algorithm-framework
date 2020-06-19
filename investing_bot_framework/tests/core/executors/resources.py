from typing import Dict, Any, List
from time import sleep
from wrapt import synchronized

from investing_bot_framework.core.workers import Worker
from investing_bot_framework.core.events.observer import Observer
from investing_bot_framework.core.executors import Executor


class TestObserver(Observer):

    def __init__(self) -> None:
        self.update_count = 0

    @synchronized
    def update(self, observable, **kwargs) -> None:
        self.update_count += 1


class TestWorkerOne(Worker):
    id = 'TestWorkerOne'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        # Simulate some work
        sleep(1)


class TestWorkerTwo(Worker):
    id = 'TestWorkerTwo'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        # Simulate some work
        sleep(1)


class TestWorkerThree(Worker):
    id = 'TestWorkerThree'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        # Simulate some work
        sleep(1)


class TestExecutor(Executor):

    def __init__(self, workers: List[Worker] = None):
        super(TestExecutor, self).__init__(max_workers=2)

        self._registered_workers = workers

    def create_workers(self) -> List[Worker]:
        return self.registered_workers

    @property
    def registered_workers(self) -> List[Worker]:
        return self._registered_workers
