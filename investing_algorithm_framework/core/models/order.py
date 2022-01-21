import logging
from abc import abstractmethod

from investing_algorithm_framework.core.models import OrderStatus

logger = logging.getLogger(__name__)


class Order:

    @abstractmethod
    def get_id(self):
        pass

    @abstractmethod
    def get_order_reference(self):
        pass

    @abstractmethod
    def set_order_reference(self, order_reference):
        pass

    @abstractmethod
    def get_target_symbol(self):
        pass

    @abstractmethod
    def get_trading_symbol(self):
        pass

    @abstractmethod
    def get_initial_price(self):
        pass

    @abstractmethod
    def set_initial_price(self, price):
        pass

    @abstractmethod
    def get_price(self):
        pass

    @abstractmethod
    def get_closing_price(self):
        pass

    @abstractmethod
    def set_closing_price(self, price):
        pass

    @abstractmethod
    def get_side(self):
        pass

    @abstractmethod
    def get_status(self) -> OrderStatus:
        pass

    @abstractmethod
    def set_status(self, status: OrderStatus):
        pass

    @abstractmethod
    def get_type(self):
        pass

    @abstractmethod
    def get_amount_target_symbol(self):
        pass

    @abstractmethod
    def get_amount_trading_symbol(self):
        pass

    @staticmethod
    @abstractmethod
    def from_dict(data):
        pass

    @abstractmethod
    def to_dict(self):
        pass

    @abstractmethod
    def split(self, amount):
        pass

    def repr(self, **fields) -> str:
        """
        Helper for __repr__
        """

        field_strings = []
        at_least_one_attached_attribute = False

        for key, field in fields.items():
            field_strings.append(f'{key}={field!r}')
            at_least_one_attached_attribute = True

        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"

        return f"<{self.__class__.__name__} {id(self)}>"

    def to_string(self):
        return self.repr(
            id=self.get_id(),
            order_reference=self.get_order_reference(),
            status=self.get_status(),
            initial_price=self.get_initial_price(),
            price=self.get_price(),
            closing_price=self.get_closing_price(),
            side=self.get_side(),
            type=self.get_type(),
            amount_target_symbol=self.get_amount_target_symbol(),
            amount_trading_symbol=self.get_amount_trading_symbol()
        )

    def __repr__(self):
        return self.to_string()
