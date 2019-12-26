import logging
import bot.setup
from time import sleep
from threading import Thread

from tests.events.setup import DummyObserver, DummyObservable, SynchronizedDummyObserver

logger = logging.getLogger(__name__)


def test_add_observer():

    observer_one = DummyObserver()
    observer_two = DummyObserver()

    observable = DummyObservable()
    observable.add_observer(observer_one)
    observable.add_observer(observer_two)

    assert len(observable.observers) == 2

    #####################################################
    #                  Edge cases                       #
    #####################################################

    # Adding the same observers again

    observable.add_observer(observer_one)
    observable.add_observer(observer_two)
    
    assert len(observable.observers) == 2

    # Adding nothing

    observable.add_observer(())

    assert len(observable.observers) == 2


def test_remove_observer():

    observer_one = DummyObserver()
    observer_two = DummyObserver()

    observable = DummyObservable()

    observable.add_observer(observer_one)
    observable.add_observer(observer_two)

    observable.remove_observer(observer_one)

    assert len(observable.observers) == 1

    observable.remove_observer(observer_two)

    assert len(observable.observers) == 0

    #####################################################
    #                  Edge cases                       #
    #####################################################

    # Removing observer that doesn't exist

    observer_three = DummyObserver()

    observable.remove_observer(observer_three)

    assert len(observable.observers) == 0

    # Removing previous observer again

    observable.remove_observer(observer_two)

    assert len(observable.observers) == 0


def test_updating():
    observer_one = DummyObserver()
    observer_two = DummyObserver()

    observable = DummyObservable()

    observable.add_observer(observer_one)
    observable.add_observer(observer_two)

    assert observer_one.update_count == 0
    assert observer_two.update_count == 0

    observable.notify_observers()

    assert observer_one.update_count == 1
    assert observer_two.update_count == 1


def start_observing(observer, observable):
    logger.debug('Starting')
    observable.add_observer(observer)
    logger.debug('Exiting')


def notify_observers(observable):
    logger.debug('Starting')
    sleep(3)
    observable.notify_observers()
    logger.debug('Exiting')


def test_threading():
    observer = SynchronizedDummyObserver()
    observable_one = DummyObservable()
    observable_two = DummyObservable()
    observable_three = DummyObservable()

    observable_one.add_observer(observer)
    observable_two.add_observer(observer)
    observable_three.add_observer(observer)

    normal_thread_one = Thread(
        name='normal_one',
        target=notify_observers,
        kwargs={
            'observable': observable_one
        }
    )

    normal_thread_two = Thread(
        name='normal_two',
        target=notify_observers,
        kwargs={
            'observable': observable_two
        }
    )

    normal_thread_three = Thread(
        name='normal_two',
        target=notify_observers,
        kwargs={
            'observable': observable_three
        }
    )

    normal_thread_one.start()
    normal_thread_two.start()
    normal_thread_three.start()

    assert normal_thread_one.is_alive()
    assert normal_thread_two.is_alive()
    assert normal_thread_three.is_alive()

    # assert daemon_thread.is_alive()
    assert observer.update_count == 0

    logger.info('main thread sleeping')

    sleep(3)

    assert observer.update_count == 3



