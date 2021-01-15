from typing import Dict, Any
from unittest import TestCase
from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.core.events import Observer


class MyWorker(Worker):

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerTwo(Worker):
    id = 'my-custom-id'

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass


class MyWorkerThree(Worker):

    def work(self, **kwargs: Dict[str, Any]) -> None:
        pass

    def get_id(self) -> str:
        return "method-id"


class MyObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        MyObserver.updated += 1


class TestBaseWorker(TestCase):

    def setUp(self) -> None:
        self.worker_one = MyWorker()
        self.worker_two = MyWorkerTwo()
        self.worker_three = MyWorkerThree()

    def test_id_generation(self):
        self.assertIsNotNone(self.worker_one.id)
        self.assertIsNotNone(self.worker_one.get_id())
        self.assertEqual("my-custom-id", self.worker_two.get_id())
        self.assertEqual("method-id", self.worker_three.get_id())

    def test_last_run_attribute(self):
        self.assertIsNone(self.worker_one.last_run)
        self.worker_one.start()
        self.assertIsNotNone(self.worker_one.last_run)

        # Store the last run
        previous_run = self.worker_one.last_run

        self.worker_one.start()
        self.assertIsNotNone(self.worker_one.last_run)

        self.assertNotEqual(previous_run, self.worker_one.last_run)

        self.assertIsNone(self.worker_two.last_run)
        self.worker_two.start()

        self.assertNotEqual(self.worker_two.last_run, self.worker_one.last_run)

    def test_observing(self) -> None:
        # Reset the values
        MyObserver.updated = 0
        self.assertIsNone(self.worker_one.last_run)
        self.worker_one.add_observer(MyObserver())
        self.assertEqual(MyObserver.updated, 0)
        self.worker_one.start()
        self.assertIsNotNone(self.worker_one.last_run)
        self.assertEqual(1, MyObserver.updated)
