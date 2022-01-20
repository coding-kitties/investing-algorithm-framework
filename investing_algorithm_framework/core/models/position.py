from abc import abstractmethod


class Position:

    @abstractmethod
    def get_symbol(self):
        pass

    @abstractmethod
    def get_orders(self):
        pass

    @abstractmethod
    def get_amount(self):
        pass
