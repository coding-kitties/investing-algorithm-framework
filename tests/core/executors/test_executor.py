from threading import active_count
from time import sleep

from tests.core.executors.resources import TestExecutor, TestWorkerOne, TestWorkerTwo, \
    TestObserver, TestWorkerThree


class TestStandardExecutor:

    def test(self) -> None:
        executor = TestExecutor(workers=[TestWorkerOne(), TestWorkerTwo()])
        observer = TestObserver()
        executor.add_observer(observer)

        # Make sure the initialization is correct
        assert len(executor.registered_workers) == 2
        assert active_count() == 1

        # Start the executor
        executor.start()

        # 3 Threads must be running
        assert executor.processing
        assert active_count() == 3

        sleep(2)

        # # After finishing only 1 thread must be active
        assert active_count(), 1
        assert not executor.processing

        # Observer must have been updated by the executor
        assert observer.update_count == 1

        # Start the executor
        executor.start()

        # 3 Threads must be running
        assert executor.processing
        assert active_count() == 3

        sleep(2)

        # After finishing only 1 thread must be active
        assert active_count() == 1
        assert not executor.processing

        # Observer must have been updated by the executor
        assert observer.update_count == 2

        executor = TestExecutor(workers=[TestWorkerOne(), TestWorkerTwo(), TestWorkerThree()])
        executor.add_observer(observer)

        # Start the executor
        executor.start()

        # 3 Threads must be running
        assert executor.processing
        assert active_count() == 3

        sleep(2)

        # After finishing only two threads must be active (main + last worker, because max workers is 2)
        assert active_count() == 2
        assert executor.processing

        sleep(1)

        # After finishing only 1 thread must be active
        assert active_count(), 1
        assert not executor.processing

        # Observer must have been updated by the executor
        assert observer.update_count == 3
