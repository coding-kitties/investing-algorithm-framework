from abc import ABC, abstractmethod


class OrderExecutor(ABC):

    @abstractmethod
    def execute_orders(self) -> None:
        pass
