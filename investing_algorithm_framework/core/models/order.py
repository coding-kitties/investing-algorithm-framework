import logging
from abc import abstractmethod

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import OrderStatus, \
    OrderType, OrderSide

logger = logging.getLogger(__name__)


class Order:

    def __init__(
        self,
        type,
        side,
        status,
        symbol=None,
        target_symbol=None,
        trading_symbol=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        price=None,
        initial_price=None,
        closing_price=None,
        reference_id=None
    ):

        if symbol is not None:

            if "/" in symbol:
                self.target_symbol = symbol.split("/")[0].upper()
                self.trading_symbol = symbol.split("/")[1].upper()
            else:
                raise OperationalException(
                    "Symbol does not contain '/' delimiter "
                )
        else:

            if target_symbol is None:
                raise OperationalException("Target symbol is not specified")

            if trading_symbol is None:
                raise OperationalException("Trading symbol is not specified")

            self.target_symbol = target_symbol.upper()
            self.trading_symbol = trading_symbol.upper()

        if side is None:
            raise OperationalException("Order side is not set")

        if type is None:
            raise OperationalException("Order type is not set")

        if status is None:
            raise OperationalException("Status is not set")

        self.reference_id = reference_id
        self.price = price
        self.side = OrderSide.from_value(side)
        self.type = OrderType.from_value(type)
        self.status = OrderStatus.from_value(status)
        self.initial_price = initial_price
        self.closing_price = closing_price

        if amount_target_symbol is None and amount_trading_symbol is None:
            raise OperationalException(
                "Amount target symbol or amount trading symbol is "
                "not specified"
            )

        if OrderType.LIMIT.equals(self.type):

            if amount_target_symbol is not None:

                if OrderStatus.PENDING.equals(self.status) \
                        or OrderStatus.TO_BE_SENT.equals(self.status):

                    if price is None:
                        raise OperationalException("Price is not specified")

                    self.amount_target_symbol = amount_target_symbol
                    self.amount_trading_symbol = amount_target_symbol * price

                elif not (OrderStatus.CANCELED.equals(self.status)
                          or OrderStatus.FAILED.equals(self.status)):

                    if initial_price is None:
                        raise OperationalException(
                            "Initial price is not specified"
                        )

                    self.amount_target_symbol = amount_target_symbol
                    self.amount_trading_symbol = \
                        amount_target_symbol * initial_price
            else:
                if OrderStatus.PENDING.equals(self.status) \
                        or OrderStatus.TO_BE_SENT.equals(self.status):

                    if price is None:
                        raise OperationalException("Price is not specified")

                    self.amount_trading_symbol = amount_trading_symbol
                    self.amount_target_symbol = amount_trading_symbol / price
                elif not (OrderStatus.CANCELED.equals(self.status)
                          or OrderStatus.FAILED.equals(self.status)):

                    if initial_price is None:
                        raise OperationalException(
                            "Initial price is not specified"
                        )

                    self.amount_trading_symbol = amount_trading_symbol
                    self.amount_target_symbol = \
                        amount_trading_symbol / initial_price
        else:
            if OrderStatus.PENDING.equals(self.status) \
                    or OrderStatus.TO_BE_SENT.equals(self.status):
                # Only expect sell orders
                self.amount_target_symbol = amount_target_symbol
                self.amount_trading_symbol = None
            elif not (OrderStatus.CANCELED.equals(self.status)
                      or OrderStatus.FAILED.equals(self.status)):

                if initial_price is None:
                    raise OperationalException(
                        "Initial price is not specified"
                    )

                # Only expect sell orders
                self.amount_target_symbol = amount_target_symbol
                self.amount_trading_symbol = \
                    amount_target_symbol * initial_price

    def set_amount_target_symbol(self, amount):
        self.amount_target_symbol = amount

        if OrderType.LIMIT.equals(self.type):

            if OrderStatus.CLOSED.equals(self.get_status()):
                self.amount_trading_symbol = \
                    self.get_initial_price() * self.get_amount_target_symbol()
            else:
                self.amount_trading_symbol = \
                    self.get_price() * self.get_amount_target_symbol()

    def set_amount_trading_symbol(self, amount):
        self.amount_trading_symbol = amount

        if OrderType.LIMIT.equals(self.type):

            if OrderStatus.CLOSED.equals(self.get_status()):
                self.amount_target_symbol = \
                    self.get_amount_trading_symbol() / self.get_initial_price()
            else:
                self.amount_target_symbol = \
                    self.get_amount_trading_symbol() / self.get_price()

    def get_reference_id(self):
        return self.reference_id

    def get_target_symbol(self):
        return self.target_symbol

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_initial_price(self):
        return self.initial_price

    def set_initial_price(self, initial_price):
        self.initial_price = initial_price

    def get_price(self):
        if self.price is not None:
            return self.price

        return 0

    def set_price(self, price):
        self.price = price

    def get_closing_price(self):
        return self.closing_price

    def set_closing_price(self, closing_price):
        self.closing_price = closing_price

    def get_side(self):
        return self.side

    def get_status(self) -> OrderStatus:
        return self.status

    def set_status(self, status):
        self.status = OrderStatus.from_value(status)

    def get_type(self):
        return self.type

    def get_amount_target_symbol(self):
        return self.amount_target_symbol

    def set_reference_id(self, reference_id):
        self.reference_id = reference_id

    def get_amount_trading_symbol(self):
        return self.amount_trading_symbol

    def update(
        self,
        status=None,
        price=None,
        initial_price=None,
        closing_price=None,
        amount_target_symbol=None,
        amount_trading_symbol=None
    ):

        if status is not None:
            self.set_status(status)

        if price is not None:
            self.set_price(price)

        if initial_price is not None:
            self.set_initial_price(initial_price)

        if closing_price is not None:
            self.set_closing_price(closing_price)

        if amount_target_symbol is not None:
            self.set_amount_target_symbol(amount_target_symbol)

        if amount_trading_symbol is not None:
            self.set_amount_trading_symbol(amount_trading_symbol)

    @staticmethod
    def from_dict(data: dict):
        return Order(
            reference_id=data.get("reference_id", None),
            target_symbol=data.get("target_symbol", None),
            trading_symbol=data.get("trading_symbol", None),
            symbol=data.get("symbol", None),
            price=data.get("price", None),
            initial_price=data.get("initial_price", None),
            closing_price=data.get("closing_price", None),
            amount_trading_symbol=data.get("amount_trading_symbol", None),
            amount_target_symbol=data.get("amount_target_symbol", None),
            status=data.get("status", None),
            type=data.get("type", None),
            side=data.get("side", None)
        )

    @abstractmethod
    def to_dict(self):
        return {
            "reference_id": self.get_reference_id(),
            "target_symbol": self.get_target_symbol(),
            "trading_symbol": self.get_trading_symbol(),
            "amount_trading_symbol": self.get_amount_trading_symbol(),
            "amount_target_symbol": self.get_amount_target_symbol(),
            "price": self.get_price(),
            "initial_price": self.get_initial_price(),
            "closing_price": self.get_closing_price(),
            "status": self.get_status().value,
            "order_type": self.get_type().value,
            "order_side": self.get_side().value
        }

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
            reference_id=self.get_reference_id(),
            symbol=f"{self.get_target_symbol()}/{self.get_trading_symbol()}",
            status=self.get_status(),
            initial_price=self.get_initial_price(),
            price=self.get_price(),
            closing_price=self.get_closing_price(),
            order_side=self.get_side(),
            order_type=self.get_type(),
            amount_target_symbol=self.get_amount_target_symbol(),
            amount_trading_symbol=self.get_amount_trading_symbol()
        )

    def __repr__(self):
        return self.to_string()
