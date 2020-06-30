from time import sleep
from typing import Dict, Any

from investing_algorithm_framework.core.workers import ScheduledWorker
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.utils import TimeUnit


class TestWorker(ScheduledWorker):
    time_unit = TimeUnit.SECOND
    time_interval = 1
    id = 'TestWorker'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestWorkerTwo(ScheduledWorker):
    time_unit = TimeUnit.SECOND
    time_interval = 1
    id = 'TestWorkerTwo'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        TestObserver.updated += 1


def test_running() -> None:
    worker = TestWorker()
    worker_two = TestWorkerTwo()

    assert worker.last_run is None
    assert TestWorker.last_run is None

    assert worker_two.last_run is None
    assert TestWorkerTwo.last_run is None

    worker.start()

    assert worker.last_run is not None
    assert TestWorker.last_run is not None

    assert worker_two.last_run is None
    assert TestWorkerTwo.last_run is None

    previous_run = worker.last_run
    sleep(1)
    worker.start()

    assert worker.last_run is not None
    assert TestWorker.last_run is not None
    assert previous_run != worker.last_run

    assert worker_two.last_run is None
    assert TestWorkerTwo.last_run is None

    worker_two.start()

    assert worker_two.last_run is not None
    assert TestWorkerTwo.last_run is not None

    assert TestWorkerTwo.last_run != TestWorker.last_run
    assert worker.last_run != worker_two.last_run


def test_observing() -> None:
    # Reset the values
    TestObserver.updated = 0
    TestWorker.last_run = None

    worker = TestWorker()
    assert worker.last_run is None
    worker.add_observer(TestObserver())
    assert TestObserver.updated == 0
    worker.start()
    assert worker.last_run is not None
    assert TestObserver.updated == 1
