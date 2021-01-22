from time import sleep
from typing import Dict, Any
from unittest import TestCase

from investing_algorithm_framework.core.workers import ScheduledWorker
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.utils import TimeUnit


class MyWorker(ScheduledWorker):
    time_unit = TimeUnit.SECOND
    time_interval = 3

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerTwo(ScheduledWorker):
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        MyObserver.updated += 1


class TestScheduledWorker(TestCase):

    def setUp(self) -> None:
        MyWorker.last_run = None
        MyWorkerTwo.last_run = None

        self.worker_one = MyWorker()
        self.worker_two = MyWorkerTwo()

    def test_running(self) -> None:
        self.assertIsNone(self.worker_one.last_run)
        self.assertIsNone(self.worker_two.last_run)

        self.worker_one.start()
        self.worker_two.start()

        self.assertIsNotNone(self.worker_one.last_run)
        self.assertIsNotNone(self.worker_two.last_run)

        previous_run_worker_one = self.worker_one.last_run
        previous_run_worker_two = self.worker_two.last_run

        sleep(1)

        self.worker_one.start()
        self.worker_two.start()
        self.assertEqual(previous_run_worker_one, self.worker_one.last_run)
        self.assertIsNotNone(self.worker_two.last_run)
        self.assertNotEqual(previous_run_worker_two, self.worker_two.last_run)

        sleep(3)

        self.worker_one.start()
        self.worker_two.start()

        self.assertNotEqual(previous_run_worker_one, self.worker_one.last_run)
        self.assertNotEqual(previous_run_worker_two, self.worker_two.last_run)

    def test_observing(self) -> None:
        MyObserver.updated = 0
        self.assertIsNone(self.worker_one.last_run)
        self.worker_one.add_observer(MyObserver())
        self.worker_two.add_observer(MyObserver())
        self.assertEqual(MyObserver.updated, 0)
        self.worker_one.start()
        self.worker_two.start()

        sleep(1)

        self.assertEqual(2, MyObserver.updated)

        self.worker_one.start()
        self.worker_two.start()

        sleep(1)

        self.assertEqual(3, MyObserver.updated)

        sleep(2)

        self.worker_one.start()
        self.worker_two.start()

        sleep(1)

        self.assertEqual(5, MyObserver.updated)
