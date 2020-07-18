from typing import Dict, Any

from investing_algorithm_framework.core.workers import ScheduledWorker, \
    RelationalWorker, Worker
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.utils import TimeUnit


class TestWorker(Worker):
    id = 'TestWorker'
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestScheduledWorker(ScheduledWorker):
    id = 'TestScheduledWorker'
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestRelationalWorkerOne(RelationalWorker):
    id = 'TestRelationalWorkerOne'
    run_after = TestWorker

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestRelationalWorkerTwo(RelationalWorker):
    id = 'TestRelationalWorkerTwo'
    run_after = TestScheduledWorker

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        TestObserver.updated += 1


def test_running() -> None:
    worker = TestWorker()
    scheduled_worker = TestScheduledWorker()
    relational_worker_one = TestRelationalWorkerOne()
    relational_worker_two = TestRelationalWorkerTwo()

    assert worker.last_run is None
    assert TestWorker.last_run is None

    assert scheduled_worker.last_run is None
    assert scheduled_worker.last_run is None

    assert relational_worker_one.last_run is None
    assert TestRelationalWorkerOne.last_run is None

    assert relational_worker_two.last_run is None
    assert TestRelationalWorkerTwo.last_run is None

    assert relational_worker_one.run_after != relational_worker_two.run_after
    assert \
        TestRelationalWorkerOne.run_after != TestRelationalWorkerTwo.run_after

    worker.start()

    assert worker.last_run is not None
    assert TestWorker.last_run is not None

    relational_worker_one.start()

    assert relational_worker_one.last_run is not None
    assert relational_worker_one.last_run is not None

    scheduled_worker.start()

    assert scheduled_worker.last_run is not None
    assert TestScheduledWorker.last_run is not None

    relational_worker_two.start()

    assert relational_worker_two.last_run is not None
    assert relational_worker_two.last_run is not None

    assert relational_worker_two.last_run != relational_worker_one.last_run
    assert TestRelationalWorkerOne.last_run != TestRelationalWorkerTwo.last_run

    previous_run = relational_worker_two.last_run

    relational_worker_two.start()

    assert relational_worker_two.last_run == previous_run


def test_observing() -> None:
    # Reset the values
    TestObserver.updated = 0
    TestRelationalWorkerOne.last_run = None

    worker = TestWorker()
    relational_worker_one = TestRelationalWorkerOne()
    relational_worker_one.add_observer(TestObserver())
    worker.start()
    assert relational_worker_one.last_run is None
    assert TestObserver.updated == 0
    relational_worker_one.start()
    assert relational_worker_one.last_run is not None
    assert TestObserver.updated == 1
