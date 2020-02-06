from abc import ABC, abstractmethod


class BotState(ABC):
    """
    Represents a state of the Bot, these states are use by the BotContext. Each implemented state represents a work
    mode for the bot.
    """

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


