import logging
from datetime import datetime
from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.order import OrderStatus, \
    OrderType, OrderSide
from investing_algorithm_framework.domain.models.order.order_fee import \
    OrderFee

logger = logging.getLogger("investing_algorithm_framework")


class Order(BaseModel):

    def __init__(
        self,
        type,
        side,
        status,
        amount,
        target_symbol=None,
        trading_symbol=None,
        price=None,
        net_gain=0,
        created_at=None,
        updated_at=None,
        trade_closed_at=None,
        trade_closed_price=None,
        external_id=None,
        filled_amount=None,
        remaining_amount=None,
        cost=None,
        fee=None,
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
        self.amount = amount
        self.net_gain = net_gain
        self.trade_closed_at = trade_closed_at
        self.trade_closed_price = trade_closed_price
        self.created_at = created_at
        self.updated_at = updated_at
        self.filled_amount = filled_amount
        self.remaining_amount = remaining_amount
        self.cost = cost
        self.fee = fee

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

    def get_amount(self):
        return self.amount

    def set_amount(self, amount):
        self.amount = amount

    def set_external_id(self, external_id):
        self.external_id = external_id

    def get_net_gain(self):
        return self.net_gain

    def set_net_gain(self, net_gain):
        self.net_gain = net_gain

    def get_trade_closed_at(self):
        return self.trade_closed_at

    def set_trade_closed_at(self, trade_closed_at):
        self.trade_closed_at = trade_closed_at

    def get_trade_closed_price(self):
        return self.trade_closed_price

    def set_trade_closed_price(self, trade_closed_price):
        self.trade_closed_price = trade_closed_price

    def get_created_at(self):
        return self.created_at

    def set_created_at(self, created_at):
        self.created_at = created_at

    def get_updated_at(self):
        return self.updated_at

    def set_updated_at(self, updated_at):
        self.updated_at = updated_at

    def get_filled_amount(self):
        return self.filled_amount

    def set_filled_amount(self, filled_amount):
        self.filled_amount = filled_amount

    def get_remaining_amount(self):
        return self.remaining_amount

    def set_remaining_amount(self, remaining_amount):
        self.remaining_amount = remaining_amount

    def get_cost(self):
        return self.cost

    def set_cost(self, cost):
        self.cost = cost

    def get_fee(self):
        return self.fee

    def set_fee(self, order_fee):
        self.fee = order_fee

    def to_dict(self):
        return {
            "external_id": self.external_id,
            "target_symbol": self.target_symbol,
            "trading_symbol": self.trading_symbol,
            "side": self.side,
            "type": self.type,
            "status": self.status,
            "price": self.price,
            "amount": self.amount,
            "net_gain": self.net_gain,
            "trade_closed_at": self.trade_closed_at,
            "trade_closed_price": self.trade_closed_price,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "filled_amount": self.filled_amount,
            "remaining_amount": self.remaining_amount,
            "cost": self.cost,
            "fee": self.fee.to_dict() if self.fee is not None else None,
        }

    @staticmethod
    def from_ccxt_order(ccxt_order):
        status = OrderStatus.from_value(ccxt_order["status"])
        target_symbol = ccxt_order.get("symbol").split("/")[0]
        trading_symbol = ccxt_order.get("symbol").split("/")[1]

        return Order(
            external_id=ccxt_order.get("id", None),
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            price=ccxt_order.get("price", None),
            amount=ccxt_order.get("amount", None),
            status=status,
            type=ccxt_order.get("type", None),
            side=ccxt_order.get("side", None),
            filled_amount=ccxt_order.get("filled", None),
            remaining_amount=ccxt_order.get("remaining", None),
            cost=ccxt_order.get("cost", None),
            fee=OrderFee.from_ccxt_fee(ccxt_order.get("fee", None)),
            created_at=datetime.strptime(ccxt_order.get("datetime", None), "%Y-%m-%dT%H:%M:%S.%fZ")
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
            side=self.side,
            type=self.type,
            amount=self.amount,
            filled_amount=self.filled_amount,
            remaining_amount=self.remaining_amount,
            cost=self.cost,
        )
