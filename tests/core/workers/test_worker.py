from typing import Dict, Any

from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.core.events import Observer


class MyWorker(Worker):
    id = 'MyWorker'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerTwo(Worker):
    id = 'MyWorkerTwo'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        MyObserver.updated += 1


def test_last_run() -> None:
    worker = MyWorker()
    assert worker.last_run is None
    worker.start()
    assert worker.last_run is not None
    previous_run = worker.last_run
    worker.start()
    assert worker.last_run is not None

    # Check if update is after previous run
    assert worker.last_run > previous_run

    worker_two = MyWorkerTwo()
    assert worker_two.last_run is None
    worker_two.start()
    assert worker_two.last_run is not None
    assert worker_two != worker.last_run


def test_observing() -> None:
    # Reset the values
    MyObserver.updated = 0
    MyWorker.last_run = None

    worker = MyWorker()
    assert worker.last_run is None
    worker.add_observer(MyObserver())
    assert MyObserver.updated == 0
    worker.start()
    assert worker.last_run is not None
    assert MyObserver.updated == 1
