import logging
from time import sleep
from threading import active_count

from bot.data import SyncDataProviderExecutor, AsyncDataProviderExecutor
from tests.data.test_executors.setup import DummyDataProviderWorker, DummyObserver

logger = logging.getLogger(__name__)


def test_initialize_executors():
    logger.info("TEST: test initialization of DataProviderExecutor ")

    data_provider_one = DummyDataProviderWorker()
    data_provider_two = DummyDataProviderWorker()
    data_provider_three = DummyDataProviderWorker()

    executor = SyncDataProviderExecutor(
        [
            data_provider_one,
            data_provider_two,
            data_provider_three
        ]
    )

    assert len(executor.registered_data_providers) == 3
    assert active_count() == 1

    executor = SyncDataProviderExecutor(
        [
            data_provider_one,
        ]
    )

    assert len(executor.registered_data_providers) == 1

    # When the DataProviderManager is initialized it should not start any threads
    assert active_count() == 1

    logger.info("TEST FINISHED")


def test_execution_sync_executor():
    logger.info("TEST: test sync executor")

    observer = DummyObserver()

    data_provider_one = DummyDataProviderWorker()
    data_provider_three = DummyDataProviderWorker()

    executor = SyncDataProviderExecutor(
        [
            data_provider_one,
            data_provider_three
        ]
    )

    executor.add_observer(observer)

    assert active_count() == 1

    executor.start()

    # Check if the observer is updated by the executor
    assert observer.update_count == 1

    data_provider_one = DummyDataProviderWorker()

    executor = SyncDataProviderExecutor(
        [
            data_provider_one,
        ]
    )

    executor.add_observer(observer)

    assert active_count() == 1

    executor.start()

    # Check if the observer is updated by the executor
    assert observer.update_count == 2

    executor.start()

    # Check if the observer is updated by the executor
    assert observer.update_count == 3

    logger.info("TEST FINISHED")


def test_execution_async_executor():
    logger.info("TEST: test async executor")

    observer = DummyObserver()

    data_provider_one = DummyDataProviderWorker()
    data_provider_three = DummyDataProviderWorker()

    executor = AsyncDataProviderExecutor(
        [
            data_provider_one,
            data_provider_three
        ]
    )

    executor.add_observer(observer)

    assert active_count() == 1

    executor.start()

    assert active_count() == 3

    sleep(2)

    # Check if the observer is updated by the executor
    assert observer.update_count == 1

    data_provider_one = DummyDataProviderWorker()

    executor = AsyncDataProviderExecutor(
        [
            data_provider_one,
        ]
    )

    executor.add_observer(observer)

    assert active_count() == 1

    executor.start()

    assert active_count() == 2

    sleep(2)

    # Check if the observer is updated by the executor
    assert observer.update_count == 2

    executor.start()

    sleep(2)

    # Check if the observer is updated by the executor
    assert observer.update_count == 3

    logger.info("TEST FINISHED")
