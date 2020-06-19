from abc import ABC, abstractmethod


class Observer(ABC):
    """
    Class Observer: Receive updates from it's observables.
    """

    @abstractmethod
    def update(self, observable, **kwargs) -> None:
        pass
