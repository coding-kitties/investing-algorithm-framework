from typing import Dict, Any
from unittest import TestCase
from time import sleep
from investing_algorithm_framework.core.workers import ScheduledWorker, \
    RelationalWorker, Worker
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.utils import TimeUnit


class MyWorker(Worker):
    id = 'MyWorker'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerTwo(ScheduledWorker):
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


worker_one = MyWorker()
worker_two = MyWorkerTwo()


class MyWorkerThree(RelationalWorker):
    run_after = worker_one

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerFour(RelationalWorker):
    run_after = worker_two

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        TestObserver.updated += 1


class TestRelationalWorker(TestCase):

    def setUp(self) -> None:
        worker_one.last_run = None
        worker_two.last_run = None

        self.relational_worker_one = MyWorkerThree()
        self.relational_worker_two = MyWorkerFour()

    def test_running(self) -> None:
        self.assertIsNone(worker_one.last_run)
        self.assertIsNone(worker_two.last_run)

        self.relational_worker_one.start()
        self.relational_worker_two.start()

        self.assertIsNone(self.relational_worker_one.last_run)
        self.assertIsNone(self.relational_worker_two.last_run)

        worker_one.start()
        worker_two.start()

        self.assertIsNotNone(worker_one.last_run)
        self.assertIsNotNone(worker_two.last_run)
        self.assertIsNone(self.relational_worker_one.last_run)
        self.assertIsNone(self.relational_worker_two.last_run)

        previous_run_worker_one = worker_one.last_run
        previous_run_worker_two = worker_two.last_run

        self.relational_worker_one.start()
        self.relational_worker_two.start()

        self.assertIsNotNone(self.relational_worker_one.last_run)
        self.assertIsNotNone(self.relational_worker_two.last_run)

        previous_run_relational_worker_one = \
            self.relational_worker_one.last_run
        previous_run_relational_worker_two = \
            self.relational_worker_two.last_run

        sleep(2)

        worker_one.start()
        worker_two.start()

        self.assertNotEqual(previous_run_worker_one, worker_one.last_run)
        self.assertNotEqual(previous_run_worker_two, worker_two.last_run)

        self.relational_worker_one.start()
        self.relational_worker_two.start()

        self.assertNotEqual(
            previous_run_relational_worker_one,
            self.relational_worker_one.last_run
        )
        self.assertNotEqual(
            previous_run_relational_worker_two,
            self.relational_worker_two.last_run
        )

    def test_observing(self) -> None:
        observer = TestObserver()

        self.relational_worker_one.add_observer(observer)
        self.relational_worker_two.add_observer(observer)

        self.relational_worker_one.start()
        self.relational_worker_two.start()

        self.assertEqual(0, observer.updated)

        worker_one.start()
        worker_two.start()

        self.assertEqual(0, observer.updated)

        self.relational_worker_one.start()
        self.relational_worker_two.start()

        self.assertEqual(2, observer.updated)

        self.relational_worker_one.start()
        self.relational_worker_two.start()
        self.assertEqual(2, observer.updated)

        sleep(2)

        worker_one.start()
        worker_two.start()

        self.assertEqual(2, observer.updated)
        self.relational_worker_one.start()
        self.relational_worker_two.start()

        self.assertEqual(4, observer.updated)
