from typing import Dict, Any
from time import sleep
from wrapt import synchronized

from investing_bot_framework.core.workers import Worker
from investing_bot_framework.core.events.observer import Observer


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
