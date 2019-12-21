from abc import ABC, abstractmethod
from bot.events.observable import Observable


class Observer(ABC):

    @abstractmethod
    def update(self, observable: Observable, **kwargs) -> None:
        """
        Receive update from subject.
        """
        pass
