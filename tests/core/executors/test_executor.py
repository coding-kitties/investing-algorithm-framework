from time import sleep
from typing import Dict, Any

from investing_algorithm_framework.core.executors import Executor
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.workers import Worker


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


class TestObserver(Observer):

    def __init__(self):
        self.update_count = 0

    def update(self, observable, **kwargs) -> None:
        self.update_count += 1


def test() -> None:
    test_worker_observer = TestObserver()
    test_worker_one = TestWorkerOne()
    test_worker_one.add_observer(test_worker_observer)
    test_worker_two = TestWorkerTwo()
    test_worker_two.add_observer(test_worker_observer)
    test_worker_three = TestWorkerThree()
    test_worker_three.add_observer(test_worker_observer)

    executor = Executor(workers=[test_worker_one, test_worker_two])
    test_executor_observer = TestObserver()
    executor.add_observer(test_executor_observer)

    # Make sure the initialization is correct
    assert len(executor.workers) == 2

    # Start the executor
    executor.start()

    # 3 Threads must be running
    sleep(3)

    # Observers must have been updated by the executor
    assert test_executor_observer.update_count == 1
    assert test_worker_observer.update_count == 2

    # Start the executor
    executor.start()

    sleep(3)

    # Observer must have been updated by the executor
    assert test_executor_observer.update_count == 2
    assert test_worker_observer.update_count == 4

    executor = Executor(
        workers=[test_worker_one, test_worker_two, test_worker_three]
    )
    executor.add_observer(test_executor_observer)

    # Start the executor
    executor.start()

    sleep(4)

    # Observers must have been updated by the executor
    assert test_executor_observer.update_count == 3
    assert test_worker_observer.update_count == 7

    executor = Executor(
        workers=[test_worker_one]
    )
    executor.add_observer(test_executor_observer)

    # Start the executor
    executor.start()

    sleep(2)

    # Observers must have been updated by the executor
    assert test_executor_observer.update_count == 4
    assert test_worker_observer.update_count == 8


class TestExceptionWorker(Worker):

    def work(self, **kwargs: Dict[str, Any]) -> None:
        raise Exception("hello")


def test_exception() -> None:
    test_worker = TestExceptionWorker()
    executor = Executor(workers=[test_worker])
    test_executor_observer = TestObserver()
    executor.add_observer(test_executor_observer)
    executor.start()
