from typing import Dict, Any
from unittest import TestCase
from time import sleep
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


class MyWorkerTwo(ScheduledWorker):
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerThree(RelationalWorker):
    run_after = MyWorker

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerFour(RelationalWorker):
    run_after = MyWorkerTwo

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class TestObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        TestObserver.updated += 1


class TestRelationalWorker(TestCase):

    def setUp(self) -> None:
        self.worker_one = MyWorker()
        self.worker_two = MyWorkerTwo()
        self.worker_three = MyWorkerThree()
        self.worker_four = MyWorkerFour()

    def test_running(self) -> None:
        self.assertIsNone(self.worker_one.last_run)
        self.assertIsNone(self.worker_two.last_run)
        self.assertIsNone(self.worker_three.last_run)

        self.worker_four.start()
        self.worker_three.start()
        self.worker_one.start()
        self.worker_two.start()

        self.assertIsNotNone(self.worker_one.last_run)
        self.assertIsNotNone(self.worker_two.last_run)
        self.assertIsNone(self.worker_three.last_run)
        self.assertIsNone(self.worker_four.last_run)

        previous_run_worker_one = self.worker_one.last_run
        previous_run_worker_two = self.worker_two.last_run

        sleep(1)

        self.worker_four.start()
        self.worker_three.start()
        self.worker_one.start()
        self.worker_two.start()

        self.assertIsNotNone(self.worker_one.last_run)
        self.assertIsNotNone(self.worker_two.last_run)
        self.assertIsNotNone(self.worker_three.last_run)
        self.assertIsNotNone(self.worker_four.last_run)

        self.assertNotEqual(previous_run_worker_one, self.worker_one.last_run)
        self.assertNotEqual(previous_run_worker_two, self.worker_two.last_run)

    def test_observing(self) -> None:
        observer = TestObserver()
        self.worker_one.add_observer(observer)
        self.worker_two.add_observer(observer)
        self.worker_one.add_observer(observer)
        self.worker_one.add_observer(observer)

        self.assertIsNone(self.worker_one.last_run)
        self.assertIsNone(self.worker_two.last_run)
        self.assertIsNone(self.worker_three.last_run)

        self.worker_four.start()
        self.worker_three.start()
        self.worker_one.start()
        self.worker_two.start()

        self.assertIsNotNone(self.worker_one.last_run)
        self.assertIsNotNone(self.worker_two.last_run)
        self.assertIsNone(self.worker_three.last_run)
        self.assertIsNone(self.worker_four.last_run)

        sleep(1)

        self.assertEqual(2, observer.updated)

        self.worker_four.start()
        self.worker_three.start()
        self.worker_one.start()
        self.worker_two.start()

        sleep(1)

        self.assertEqual(4, observer.updated)

