from abc import abstractmethod

from bot.executors.executor import Executor


class SingleExecutor(Executor):
    """
    SingleExecutor class: functions as an abstract class that will handle the executions of a single function.
    """

    def __init__(self) -> None:
        super(SingleExecutor, self).__init__()

    def start(self) -> None:
        self.run_job()
        self.notify_observers()

    @abstractmethod
    def run_job(self) -> None:
        pass
