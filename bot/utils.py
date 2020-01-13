import threading
import sys
from wrapt import synchronized
from threading import Thread
from pandas import DataFrame


class Singleton(type):
    _instances = {}

    @synchronized
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class StoppableThread(Thread):
    """
    Class StoppableThread: Functions as a wrapper around a thread to add stop function
    """

    def __init__(self, *args, **keywords):
        Thread.__init__(self, *args, **keywords)
        self.killed = False

    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        if event == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True


class DataSource:

    def __init__(self, data_provider_id: str,  data: DataFrame) -> None:
        self._data = data
        self._data_provider_id = data_provider_id

    @property
    def data(self) -> DataFrame:
        return self._data

    @property
    def data_provider_id(self) -> str:
        return self._data_provider_id


