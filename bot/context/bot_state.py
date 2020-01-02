from abc import ABC, abstractmethod


class BotState(ABC):

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def reconfigure(self):
        pass


