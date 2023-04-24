import logging

from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.order import OrderStatus, \
    OrderType, OrderSide

logger = logging.getLogger(__name__)


class Order(BaseModel):

    def __init__(
        self,
        type,
        side,
        status,
        target_symbol=None,
        trading_symbol=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        price=None,
        external_id=None
    ):

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

        self.external_id = external_id
        self.price = price
        self.side = OrderSide.from_value(side).value
        self.type = OrderType.from_value(type).value
        self.status = OrderStatus.from_value(status).value

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

                    self.amount_target_symbol = amount_target_symbol
                    self.amount_trading_symbol = amount_target_symbol * price
            else:
                if OrderStatus.PENDING.equals(self.status) \
                        or OrderStatus.TO_BE_SENT.equals(self.status):

                    if price is None:
                        raise OperationalException("Price is not specified")

                    self.amount_trading_symbol = amount_trading_symbol
                    self.amount_target_symbol = amount_trading_symbol / price
                elif not (OrderStatus.CANCELED.equals(self.status)
                          or OrderStatus.FAILED.equals(self.status)):

                    self.amount_trading_symbol = amount_trading_symbol
                    self.amount_target_symbol = amount_trading_symbol / price
        else:
            if OrderStatus.PENDING.equals(self.status) \
                    or OrderStatus.TO_BE_SENT.equals(self.status):
                # Only expect sell orders
                self.amount_target_symbol = amount_target_symbol
                self.amount_trading_symbol = None
            elif not (OrderStatus.CANCELED.equals(self.status)
                      or OrderStatus.FAILED.equals(self.status)):
                # Only expect sell orders
                self.amount_target_symbol = amount_target_symbol
                self.amount_trading_symbol = amount_target_symbol * price

    def set_amount_target_symbol(self, amount):
        self.amount_target_symbol = amount

        if OrderType.LIMIT.equals(self.type):

            if OrderStatus.CLOSED.equals(self.get_status()):
                self.amount_trading_symbol = \
                    self.get_price() * self.get_amount_target_symbol()
            else:
                self.amount_trading_symbol = \
                    self.get_price() * self.get_amount_target_symbol()

    def set_amount_trading_symbol(self, amount):
        self.amount_trading_symbol = amount

        if OrderType.LIMIT.equals(self.type):

            if OrderStatus.CLOSED.equals(self.get_status()):
                self.amount_target_symbol = \
                    self.get_amount_trading_symbol() / self.get_price()
            else:
                self.amount_target_symbol = \
                    self.get_amount_trading_symbol() / self.get_price()

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

    def get_side(self):
        return self.side

    def get_status(self) -> OrderStatus:
        return self.status

    def set_status(self, status):
        self.status = OrderStatus.from_value(status).value

    def get_type(self):
        return self.type

    def get_amount_target_symbol(self):
        return self.amount_target_symbol

    def set_external_id(self, external_id):
        self.external_id = external_id

    def get_amount_trading_symbol(self):
        return self.amount_trading_symbol

    def to_dict(self):
        return {
            "external_id": self.external_id,
            "target_symbol": self.target_symbol,
            "trading_symbol": self.trading_symbol,
            "side": self.side,
            "type": self.type,
            "status": self.status,
            "price": self.price,
            "amount_target_symbol": self.amount_target_symbol,
            "amount_trading_symbol": self.amount_trading_symbol
        }

    @staticmethod
    def from_ccxt_order(ccxt_order):
        status = OrderStatus.PENDING.value

        if ccxt_order["status"] == "open":
            status = OrderStatus.PENDING.value
        if ccxt_order["status"] == "closed":
            status = OrderStatus.SUCCESS.value
        if ccxt_order["status"] == "canceled":
            status = OrderStatus.CANCELED.value
        if ccxt_order["status"] == "expired":
            status = OrderStatus.FAILED.value
        if ccxt_order["status"] == "rejected":
            status = OrderStatus.FAILED.value

        target_symbol = ccxt_order.get("symbol").split("/")[0]
        trading_symbol = ccxt_order.get("symbol").split("/")[1]

        return Order(
            external_id=ccxt_order.get("id", None),
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            price=ccxt_order.get("price", None),
            amount_target_symbol=ccxt_order.get("amount", None),
            status=status,
            type=ccxt_order.get("type", None),
            side=ccxt_order.get("side", None)
        )

    def __repr__(self):

        if not hasattr(self, "id"):
            id_value = "ccxt external order"
        else:
            id_value = self.id

        return self.repr(
            id=id_value,
            external_id=self.external_id,
            status=self.status,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            price=self.price,
            amount_trading_symbol=self.amount_trading_symbol,
            amount_target_symbol=self.amount_target_symbol,
        )

    def initialize_amount_target_symbol(self):

        if not OrderType.MARKET.equals(self.type) \
                and self.price is None:
            raise OperationalException("Initial price is not set")

        if self.amount_target_symbol is None:
            self.amount_target_symbol = \
                self.amount_trading_symbol / self.price

    def initialize_amount_trading_symbol(self):

        if OrderType.MARKET.equals(self.type):
            if OrderStatus.SUCCESS.equals(self.status) \
                    and self.price is None:
                raise OperationalException("Initial price is not set")
        else:
            if self.amount_trading_symbol is None:
                self.amount_trading_symbol = \
                    self.amount_target_symbol * self.price
