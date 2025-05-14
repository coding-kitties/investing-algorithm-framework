import logging
from datetime import datetime, timezone

from dateutil.parser import parse

from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.order.order_side import \
    OrderSide
from investing_algorithm_framework.domain.models.order.order_status import \
    OrderStatus
from investing_algorithm_framework.domain.models.order.order_type import \
    OrderType

logger = logging.getLogger("investing_algorithm_framework")


class Order(BaseModel):
    """
    Order model class to represent an order of the trading bot
    """
    def __init__(
        self,
        order_type,
        order_side,
        amount,
        status=OrderStatus.CREATED.value,
        target_symbol=None,
        trading_symbol=None,
        price=None,
        created_at=None,
        updated_at=None,
        external_id=None,
        cost=None,
        filled=None,
        remaining=None,
        fee=None,
        position_id=None,
        order_fee=None,
        order_fee_currency=None,
        order_fee_rate=None,
        id=None
    ):
        if target_symbol is None:
            raise OperationalException("Target symbol is not specified")

        if trading_symbol is None:
            raise OperationalException("Trading symbol is not specified")

        self.target_symbol = target_symbol.upper()
        self.trading_symbol = trading_symbol.upper()

        if order_side is None:
            raise OperationalException("Order side is not set")

        if order_type is None:
            raise OperationalException("Order type is not set")

        if status is None:
            raise OperationalException("Status is not set")

        self.created_at = created_at
        self.updated_at = updated_at

        if self.created_at is None:
            self.created_at = datetime.now(tz=timezone.utc)

        if self.updated_at is None:
            self.updated_at = datetime.now(tz=timezone.utc)

        self.external_id = external_id
        self.price = price
        self.order_side = OrderSide.from_value(order_side).value
        self.order_type = OrderType.from_value(order_type).value
        self.status = OrderStatus.from_value(status).value
        self.position_id = position_id
        self.amount = amount
        self.filled = filled
        self.remaining = remaining
        self.fee = fee
        self._available_amount = self.filled
        self.order_fee = order_fee
        self.order_fee_currency = order_fee_currency
        self.order_fee_rate = order_fee_rate
        self.id = id
        self.cost = cost

    def get_id(self):
        return self.id

    def get_external_id(self):
        return self.external_id

    def get_target_symbol(self):
        return self.target_symbol

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_price(self):
        if self.price is not None:
            return self.price

        return 0

    def set_price(self, price):
        self.price = price

    def get_order_fee_currency(self):
        return self.order_fee_currency

    def set_order_fee_currency(self, order_fee_currency):
        self.order_fee_currency = order_fee_currency

    def get_order_fee_rate(self):
        return self.order_fee_rate

    def set_order_fee_rate(self, order_fee_rate):
        self.order_fee_rate = order_fee_rate

    def get_order_fee(self):
        return self.order_fee

    def set_order_fee(self, order_fee):
        self.order_fee = order_fee

    def get_order_size(self):
        return self.order_side

    def get_status(self) -> OrderStatus:
        return self.status

    def set_status(self, status):
        self.status = OrderStatus.from_value(status).value

    def get_order_type(self):
        return self.order_type

    def get_order_side(self):
        return self.order_side

    def get_amount(self):
        return self.amount

    def set_amount(self, amount):
        self.amount = amount

    def set_external_id(self, external_id):
        self.external_id = external_id

    def get_created_at(self):
        return self.created_at

    def set_created_at(self, created_at):
        self.created_at = created_at

    def get_updated_at(self):
        return self.updated_at

    def set_updated_at(self, updated_at):
        self.updated_at = updated_at

    def get_filled(self):

        if self.filled is None:
            return 0

        return self.filled

    def set_filled(self, filled):
        self.filled = filled

    def get_remaining(self):

        if self.remaining is None:
            return self.get_amount() - self.get_filled()

        return self.remaining

    def set_remaining(self, remaining):
        self.remaining = remaining

    def get_fee(self):
        return self.fee

    def set_fee(self, order_fee):
        self.fee = order_fee

    def get_symbol(self):
        return (self.get_target_symbol().upper() + "/"
                + self.get_trading_symbol().upper())

    def get_available_amount(self):

        if self._available_amount is None:
            return self.get_filled()

        return self._available_amount

    @property
    def available_amount(self):
        return self.get_available_amount()

    def set_available_amount(self, available_amount):
        self._available_amount = available_amount

    @available_amount.setter
    def available_amount(self, available_amount):
        self.set_available_amount(available_amount)

    def to_dict(self, datetime_format=None):
        """
        Convert the Order object to a dictionary

        Args:
            datetime_format (str): The format to use for the datetime fields.
                If None, the datetime fields will be returned as is.
                Defaults to None.

        Returns:
            dict: A dictionary representation of the Order object.
        """

        if datetime_format is not None:
            created_at = self.created_at.strftime(datetime_format) \
                if self.created_at else None
            updated_at = self.updated_at.strftime(datetime_format) \
                if self.updated_at else None
        else:
            created_at = self.created_at
            updated_at = self.updated_at

        return {
            "id": self.id,
            "external_id": self.external_id,
            "target_symbol": self.target_symbol,
            "trading_symbol": self.trading_symbol,
            "order_side": self.order_side,
            "order_type": self.order_type,
            "status": self.status,
            "price": self.price,
            "amount": self.amount,
            "created_at": created_at,
            "updated_at": updated_at,
            "cost": self.cost,
            "filled": self.filled,
            "remaining": self.remaining,
            "order_fee_currency": self.order_fee_currency,
            "order_fee_rate": self.order_fee_rate,
            "order_fee": self.order_fee,
        }

    @staticmethod
    def from_dict(data: dict):
        created_at = data.get("created_at", None)
        updated_at = data.get("updated_at", None)
        symbol = data.get("symbol", None)

        if symbol is not None:
            target_symbol = symbol.split("/")[0]
            trading_symbol = symbol.split("/")[1]
        else:
            target_symbol = data.get("target_symbol", None)
            trading_symbol = data.get("trading_symbol", None)

        if created_at is not None:
            created_at = parse(created_at)

        if updated_at is not None:
            updated_at = parse(updated_at)

        order = Order(
            external_id=data.get("id", None),
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            price=data.get("price", None),
            amount=data.get("amount", None),
            status=data.get("status", None),
            order_type=data.get("order_type", None),
            order_side=data.get("order_side", None),
            filled=data.get("filled", None),
            remaining=data.get("remaining", None),
            fee=data.get("fee", None),
            created_at=created_at,
            updated_at=updated_at,
            order_fee=data.get("order_fee", None),
            order_fee_currency=data.get("order_fee_currency", None),
            order_fee_rate=data.get("order_fee_rate", None),
            id=data.get("id", None)
        )
        return order

    @staticmethod
    def from_ccxt_order(ccxt_order):
        """
        Create an Order object from a ccxt order object
        :param ccxt_order: ccxt order object
        :return: Order object
        """
        status = OrderStatus.from_value(ccxt_order["status"])
        target_symbol = ccxt_order.get("symbol").split("/")[0]
        trading_symbol = ccxt_order.get("symbol").split("/")[1]
        ccxt_fee = ccxt_order.get("fee", None)
        order_fee = None
        order_fee_currency = None
        order_fee_rate = None

        if ccxt_fee is not None:
            order_fee = ccxt_fee.get("cost", None)
            order_fee_currency = ccxt_fee.get("currency", None)
            order_fee_rate = ccxt_fee.get("rate", None)

        return Order(
            external_id=ccxt_order.get("id", None),
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            price=ccxt_order.get("price", None),
            amount=ccxt_order.get("amount", None),
            status=status,
            cost=ccxt_order.get("cost", None),
            order_type=ccxt_order.get("type", None),
            order_side=ccxt_order.get("side", None),
            filled=ccxt_order.get("filled", None),
            remaining=ccxt_order.get("remaining", None),
            order_fee=order_fee,
            order_fee_currency=order_fee_currency,
            order_fee_rate=order_fee_rate,
            created_at=parse(ccxt_order.get("datetime", None))
        )

    def __repr__(self):

        if not hasattr(self, "id"):
            id_value = "ccxt external order"
        else:
            id_value = self.id

        return self.repr(
            id=id_value,
            price=self.get_price(),
            amount=self.get_amount(),
            external_id=self.external_id,
            status=self.status,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            order_side=self.order_side,
            order_type=self.order_type,
            filled=self.get_filled(),
            remaining=self.get_remaining(),
            created_at=self.get_created_at(),
            updated_at=self.get_updated_at(),
        )

    def get_size(self):
        """
        Get the size of the order

        Returns:
            float: The size of the order
        """
        return self.get_amount() * self.get_price() \
            if self.get_price() is not None else 0
