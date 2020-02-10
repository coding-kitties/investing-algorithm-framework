from abc import ABC, abstractmethod


class BotState(ABC):

    def __init__(self, context) -> None:
        self._bot_context = context

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @property
    def context(self):
        return self._bot_context

    @abstractmethod
    def reconfigure(self):
        pass


