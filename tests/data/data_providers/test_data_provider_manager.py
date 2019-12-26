from time import sleep
import logging
from threading import active_count
from bot.data.data_provider_manager import DataProviderManager

from tests.data.data_providers.setup import DummyDataProvider, DummyObserver

logger = logging.getLogger(__name__)


def test_initialize_data_providers():
    logger.info("TEST: test_initialize_data_providers")

    data_provider_one = DummyDataProvider()
    data_provider_two = DummyDataProvider()
    data_provider_three = DummyDataProvider()

    manager = DataProviderManager(
        [
            data_provider_one,
            data_provider_two,
            data_provider_three
        ]
    )

    assert len(manager.registered_data_providers) == 3

    # When the DataProviderManager is initialized it should not start any threads
    assert active_count() == 1

    logger.info("TEST FINISHED: test_initialize_data_providers")


def test_start_stop_data_providers():
    logger.info("TEST: test_start_stop_data_providers")

    data_provider_one = DummyDataProvider()
    data_provider_two = DummyDataProvider()
    data_provider_three = DummyDataProvider()

    manager = DataProviderManager([data_provider_one, data_provider_two, data_provider_three], max_workers=2)

    manager.start_data_providers()

    # Wait for initialization
    sleep(1)

    assert active_count() == 3

    manager.stop_data_providers()

    # Should stop all the worker threads immediately
    assert active_count() == 1
    logger.info("TEST FINISHED: test_start_stop_data_providers")


def test_observable_data_providers():
    logger.info("TEST: test_observable_data_providers")

    observer = DummyObserver()

    data_provider_one = DummyDataProvider()
    data_provider_two = DummyDataProvider()
    data_provider_three = DummyDataProvider()

    manager = DataProviderManager([data_provider_one, data_provider_two, data_provider_three], max_workers=2)
    manager.add_observer(observer)

    assert len(manager.registered_data_providers) == 3

    # Make sure that only the main thread is running
    assert active_count() == 1

    manager.start_data_providers()

    # Main thread + 2 workers
    assert active_count() == 3

    # The workers should be finished after 3 seconds, distributed over 2 iterations makes up for 6 seconds.
    # To be safe we wait 7 seconds
    sleep(7)

    # All workers should have stopped by now
    assert active_count() == 1

    # Check if the observer is updated by the manager
    assert observer.update_count == 1
    logger.info("TEST FINISHED: test_observable_data_providers")








