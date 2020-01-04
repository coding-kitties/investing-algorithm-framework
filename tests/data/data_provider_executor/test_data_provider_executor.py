import logging
from time import sleep
from threading import active_count

from bot.data import DataProviderExecutor
from tests.data.data_provider_executor.setup import DummyDataProvider, DummyObserver

logger = logging.getLogger(__name__)


def test_initialize_data_providers():
    logger.info("TEST: test initialization of DataProviderExecutor ")

    data_provider_one = DummyDataProvider()
    data_provider_two = DummyDataProvider()
    data_provider_three = DummyDataProvider()

    executor = DataProviderExecutor(
        [
            data_provider_one,
            data_provider_two,
            data_provider_three
        ]
    )

    assert len(executor.registered_data_providers) == 3

    # When the DataProviderManager is initialized it should not start any threads
    assert active_count() == 1

    executor = DataProviderExecutor(
        [
            data_provider_one,
        ]
    )

    assert len(executor.registered_data_providers) == 1

    # When the DataProviderManager is initialized it should not start any threads
    assert active_count() == 1

    logger.info("TEST FINISHED")


def test_start_stop_data_providers():
    logger.info("TEST: test_start_stop_data_providers")

    data_provider_one = DummyDataProvider()
    data_provider_two = DummyDataProvider()
    data_provider_three = DummyDataProvider()

    executor = DataProviderExecutor(
        [
            data_provider_one,
            data_provider_two,
            data_provider_three
        ]
    )

    executor.start()

    # Wait for initialization
    sleep(1)

    assert active_count() == 3

    executor.stop()

    # Should stop all the worker threads immediately
    assert active_count() == 1

    executor = DataProviderExecutor(
        [
            data_provider_one,
        ]
    )

    executor.start()

    # Wait for initialization
    sleep(1)

    assert active_count() == 2

    executor.stop()

    # Should stop all the worker threads immediately
    assert active_count() == 1

    logger.info("TEST FINISHED")


def test_observable_data_providers():
    logger.info("TEST: test_observable_data_providers")

    observer = DummyObserver()

    data_provider_one = DummyDataProvider()
    data_provider_two = DummyDataProvider()
    data_provider_three = DummyDataProvider()

    executor = DataProviderExecutor(
        [
            data_provider_one,
            data_provider_two,
            data_provider_three
        ]
    )

    executor.add_observer(observer)

    assert len(executor.registered_data_providers) == 3

    # Make sure that only the main thread is running
    assert active_count() == 1

    executor.start()

    # Main thread + 2 context
    assert active_count() == 3

    # The context should be finished after 3 seconds, distributed over 2 iterations makes up for 6 seconds.
    # To be safe we wait 7 seconds
    sleep(7)

    # All context should have stopped by now
    assert active_count() == 1

    # Check if the observer is updated by the manager
    assert observer.update_count == 1
    logger.info("TEST FINISHED")








