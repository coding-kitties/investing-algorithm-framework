from typing import Dict, Any

from investing_algorithm_framework.core.workers import ScheduledWorker, \
    RelationalWorker, Worker
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.utils import TimeUnit


class MyWorker(Worker):
    id = 'MyWorker'
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyScheduledWorker(ScheduledWorker):
    id = 'MyScheduledWorker'
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyRelationalWorkerOne(RelationalWorker):
    id = 'MyRelationalWorkerOne'
    run_after = MyWorker

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyRelationalWorkerTwo(RelationalWorker):
    id = 'MyRelationalWorkerTwo'
    run_after = MyScheduledWorker

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        TestObserver.updated += 1


def test_running() -> None:
    worker = MyWorker()
    scheduled_worker = MyScheduledWorker()
    relational_worker_one = MyRelationalWorkerOne()
    relational_worker_two = MyRelationalWorkerTwo()

    assert worker.last_run is None
    assert MyWorker.last_run is None

    assert scheduled_worker.last_run is None
    assert scheduled_worker.last_run is None

    assert relational_worker_one.last_run is None
    assert MyRelationalWorkerOne.last_run is None

    assert relational_worker_two.last_run is None
    assert MyRelationalWorkerTwo.last_run is None

    assert relational_worker_one.run_after != relational_worker_two.run_after
    assert \
        MyRelationalWorkerOne.run_after != MyRelationalWorkerTwo.run_after

    worker.start()

    assert worker.last_run is not None
    assert MyWorker.last_run is not None

    relational_worker_one.start()

    assert relational_worker_one.last_run is not None
    assert relational_worker_one.last_run is not None

    scheduled_worker.start()

    assert scheduled_worker.last_run is not None
    assert MyScheduledWorker.last_run is not None

    relational_worker_two.start()

    assert relational_worker_two.last_run is not None
    assert relational_worker_two.last_run is not None

    assert relational_worker_two.last_run != relational_worker_one.last_run
    assert MyRelationalWorkerOne.last_run != MyRelationalWorkerTwo.last_run

    previous_run = relational_worker_two.last_run

    relational_worker_two.start()

    assert relational_worker_two.last_run == previous_run


def test_observing() -> None:
    # Reset the values
    TestObserver.updated = 0
    MyRelationalWorkerOne.last_run = None

    worker = MyWorker()
    relational_worker_one = MyRelationalWorkerOne()
    relational_worker_one.add_observer(TestObserver())
    worker.start()
    assert relational_worker_one.last_run is None
    assert TestObserver.updated == 0
    relational_worker_one.start()
    assert relational_worker_one.last_run is not None
    assert TestObserver.updated == 1
