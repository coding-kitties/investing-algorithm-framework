import threading
from abc import ABC, abstractmethod
from threading import Thread
from functools import wraps
from datetime import timedelta


def singleton(class_):
    instances = {}

    def get_instance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]

    return get_instance


class ScheduledThread(Thread):

    def __init__(self, interval, execute, *args, **kwargs):
        threading.Thread.__init__(self)
        self.daemon = False
        self.stopped = threading.Event()
        self.interval = interval
        self.execute = execute
        self.args = args
        self.kwargs = kwargs

    def stop(self):
        print("Thread stopping")
        self.stopped.set()
        self.join()
        print("Thead stopped")

    def run(self):
        while not self.stopped.wait(self.interval.total_seconds()):
            self.execute(*self.args, **self.kwargs)


def synchronized(func):
    @wraps(func)
    def synchronization_handler(*args):
        self = args[0]
        self.mutex.acquire()
        # print(method.__name__, 'acquired')
        try:
            return func(*args)
        finally:
            self.mutex.release()
            # print(method.__name__, 'released')

    return synchronization_handler


def synchronize(provided_class, names=None):
    """
        Synchronize methods in the given class.
        Only synchronize the methods whose names are
        given, or all methods if names=None.
    """
    if type(names) == type(''):
        names = names.split()

    for (name, val) in provided_class.__dict__.items():

        if callable(val) and name != '__init__' and (names is None or name in names):
            print("synchronizing", name)
            provided_class.__dict__[name] = synchronized(val)


# You can create your own self.mutex, or inherit
# from this class:
class Synchronization:

    def __init__(self):
        self.mutex = threading.RLock()





