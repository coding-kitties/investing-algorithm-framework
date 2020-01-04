from abc import abstractmethod

from bot.events.observable import Observable


class Executor(Observable):
    """
    Executor class: functions as an interface that will handle the executions of functions.
    """

    @abstractmethod
    def start(self) -> None:
        pass
