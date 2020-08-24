from time import sleep
from typing import Dict, Any

from investing_algorithm_framework.core.workers import ScheduledWorker
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.utils import TimeUnit


class MyWorker(ScheduledWorker):
    time_unit = TimeUnit.SECOND
    time_interval = 1
    id = 'MyWorker'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerTwo(ScheduledWorker):
    time_unit = TimeUnit.SECOND
    time_interval = 1
    id = 'MyWorkerTwo'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        MyObserver.updated += 1


def test_running() -> None:
    worker = MyWorker()
    worker_two = MyWorkerTwo()

    assert worker.last_run is None
    assert MyWorker.last_run is None

    assert worker_two.last_run is None
    assert MyWorkerTwo.last_run is None

    worker.start()

    assert worker.last_run is not None
    assert MyWorker.last_run is not None

    assert worker_two.last_run is None
    assert MyWorkerTwo.last_run is None

    previous_run = worker.last_run
    sleep(1)
    worker.start()

    assert worker.last_run is not None
    assert MyWorker.last_run is not None
    assert previous_run != worker.last_run

    assert worker_two.last_run is None
    assert MyWorkerTwo.last_run is None

    worker_two.start()

    assert worker_two.last_run is not None
    assert MyWorkerTwo.last_run is not None

    assert MyWorkerTwo.last_run != MyWorker.last_run
    assert worker.last_run != worker_two.last_run


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
