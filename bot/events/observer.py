from abc import ABC, abstractmethod


class Observer(ABC):

    @abstractmethod
    def update(self, observable, **kwargs) -> None:
        """
        Receive update from subject.
        """
        pass
