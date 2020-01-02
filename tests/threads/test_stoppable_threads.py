from time import sleep
from threading import active_count
from bot.utils import StoppableThread


def dummy_function():
    a = 0
    while 1:
        a = 2


# Function to test if the thread can be stopped
def test_stoppable_thread():

    job = StoppableThread(target=dummy_function)
    job.start()

    # Main thread and new thread
    assert active_count() == 2

    # Make sure it runs
    sleep(2)

    job.kill()

    job.join()

    assert active_count() == 1
    assert not job.is_alive()