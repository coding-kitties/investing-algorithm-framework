# from threading import active_count
# from typing import Dict, Any, List
# from unittest import TestCase
# from time import sleep
# from wrapt import synchronized
#
# from investing_bot_framework.core.workers import Worker
# from investing_bot_framework.core.executors import Executor
# from investing_bot_framework.core.events.observer import Observer
#
#
# class TestObserver(Observer):
#
#     def __init__(self) -> None:
#         self.update_count = 0
#
#     @synchronized
#     def update(self, observable, **kwargs) -> None:
#         self.update_count += 1
#
#
# class TestWorkerOne(Worker):
#     id = 'TestWorkerOne'
#
#     def work(self, **kwargs: Dict[str, Any]) -> None:
#         # Simulate some work
#         sleep(1)
#
#
# class TestWorkerTwo(Worker):
#     id = 'TestWorkerTwo'
#
#     def work(self, **kwargs: Dict[str, Any]) -> None:
#         # Simulate some work
#         sleep(1)
#
#
# class TestWorkerThree(Worker):
#     id = 'TestWorkerThree'
#
#     def work(self, **kwargs: Dict[str, Any]) -> None:
#         # Simulate some work
#         sleep(1)
#
#
# class TestExecutor(Executor):
#
#     def __init__(self, workers: List[Worker] = None):
#         super(TestExecutor, self).__init__(max_workers=2)
#
#         self._registered_workers = workers
#
#     def create_workers(self) -> List[Worker]:
#         return self.registered_workers
#
#     @property
#     def registered_workers(self) -> List[Worker]:
#         return self._registered_workers
#
#
# class TestStandardExecutor(TestCase):
#
#     def test(self) -> None:
#         executor = TestExecutor(workers=[TestWorkerOne(), TestWorkerTwo()])
#         observer = TestObserver()
#         executor.add_observer(observer)
#
#         # Make sure the initialization is correct
#         self.assertEqual(len(executor.registered_workers), 2)
#         self.assertEqual(active_count(), 1)
#
#         # Start the executor
#         executor.start()
#
#         # 3 Threads must be running
#         self.assertTrue(executor.processing)
#         self.assertEqual(active_count(), 3)
#
#         sleep(2)
#
#         # After finishing only 1 thread must be active
#         self.assertEqual(active_count(), 1)
#         self.assertFalse(executor.processing)
#
#         # Observer must have been updated by the executor
#         self.assertEqual(observer.update_count, 1)
#
#         # Start the executor
#         executor.start()
#
#         # 3 Threads must be running
#         self.assertTrue(executor.processing)
#         self.assertEqual(active_count(), 3)
#
#         sleep(2)
#
#         # After finishing only 1 thread must be active
#         self.assertEqual(active_count(), 1)
#         self.assertFalse(executor.processing)
#
#         # Observer must have been updated by the executor
#         self.assertEqual(observer.update_count, 2)
#
#         executor = TestExecutor(workers=[TestWorkerOne(), TestWorkerTwo(), TestWorkerThree()])
#         executor.add_observer(observer)
#
#         # Start the executor
#         executor.start()
#
#         # 3 Threads must be running
#         self.assertTrue(executor.processing)
#         self.assertEqual(active_count(), 3)
#
#         sleep(2)
#
#         # After finishing only two threads must be active (main + last worker, because max workers is 2)
#         self.assertEqual(active_count(), 2)
#         self.assertTrue(executor.processing)
#
#         sleep(1)
#
#         # After finishing only 1 thread must be active
#         self.assertEqual(active_count(), 1)
#         self.assertFalse(executor.processing)
#
#         # Observer must have been updated by the executor
#         self.assertEqual(observer.update_count, 3)
#
#
#
#
#
#         # def test_execution_executor():
# #     logger.info("TEST: test DataProviderExecutor execution")
# #
# #     observer = DummyObserver()
# #
# #     data_provider_one = DummyDataProviderWorker()
# #     data_provider_three = DummyDataProviderWorker()
# #
# #     executor = DataProviderExecutor(
# #         [
# #             data_provider_one,
# #             data_provider_three
# #         ]
# #     )
# #
# #     executor.add_observer(observer)
# #
# #     assert active_count() == 1
# #
# #
# #     assert active_count() == 3
# #
# #     sleep(2)
# #
# #     # Check if the observer is updated by the executor
# #     assert observer.update_count == 1
# #
# #     data_provider_one = DummyDataProviderWorker()
# #
# #     executor = DataProviderExecutor(
# #         [
# #             data_provider_one,
# #         ]
# #     )
# #
# #     executor.add_observer(observer)
# #
# #     assert active_count() == 1
# #
# #     executor.start()
# #
# #     assert active_count() == 2
# #
# #     sleep(2)
# #
# #     # Check if the observer is updated by the executor
# #     assert observer.update_count == 2
# #
# #     executor.start()
# #
# #     sleep(2)
# #
# #     # Check if the observer is updated by the executor
# #     assert observer.update_count == 3
# #
# #     logger.info("TEST FINISHED")