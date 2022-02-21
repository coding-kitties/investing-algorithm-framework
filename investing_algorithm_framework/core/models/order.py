import logging
from abc import abstractmethod

from investing_algorithm_framework.core.models import OrderStatus, \
    OrderType, OrderSide
from investing_algorithm_framework.core.exceptions import OperationalException
logger = logging.getLogger(__name__)


class Order:

    def __init__(
        self,
        target_symbol,
        trading_symbol,
        order_type,
        order_side,
        status,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        price=None,
        initial_price=None,
        closing_price=None,
        id=None,
        reference_id=None
    ):
        self.id = id
        self.reference_id = reference_id
        self.target_symbol = target_symbol
        self.trading_symbol = trading_symbol
        self.price = price
        self.amount_trading_symbol = amount_trading_symbol
        self.amount_target_symbol = amount_target_symbol
        self.order_side = order_side
        self.order_type = order_type
        self.status = status
        self.initial_price = initial_price
        self.closing_price = closing_price

        if OrderType.MARKET.equals(self.order_type):

            if self.amount_target_symbol is None:
                raise OperationalException(
                    "Amount target symbol is not specified"
                )

        else:

            if self.amount_target_symbol is None \
                    and self.amount_trading_symbol is None:
                raise OperationalException(
                    "Amount trading symbol and amount target "
                    "symbol are not specified"
                )

            if self.amount_trading_symbol is not None:
                self.amount_target_symbol = \
                    self.price / self.amount_trading_symbol
            else:
                self.amount_trading_symbol = \
                    self.price * self.amount_target_symbol

    def get_id(self):
        return self.id

    def get_reference_id(self):
        return self.reference_id

    def get_target_symbol(self):
        return self.target_symbol

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_initial_price(self):
        return self.initial_price

    def get_price(self):
        return self.price

    def get_closing_price(self):
        return self.closing_price

    def get_side(self):
        return self.order_side

    def get_status(self) -> OrderStatus:
        return self.status

    def get_type(self):
        return self.order_type

    def get_amount_target_symbol(self):
        return self.amount_target_symbol

    def get_amount_trading_symbol(self):
        return self.amount_trading_symbol

    @staticmethod
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
            reference_id=self.get_reference_id(),
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
