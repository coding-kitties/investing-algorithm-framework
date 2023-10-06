import logging
from datetime import datetime

from investing_algorithm_framework.domain.decimal_parsing \
    import parse_string_to_decimal, parse_decimal_to_string
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
        order_type,
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
        trade_closed_amount=None,
        external_id=None,
        filled_amount=None,
        remaining_amount=None,
        cost=None,
        fee=None,
        position_id=None,
    ):
        if target_symbol is None:
            raise OperationalException("Target symbol is not specified")

        if trading_symbol is None:
            raise OperationalException("Trading symbol is not specified")

        self.target_symbol = target_symbol.upper()
        self.trading_symbol = trading_symbol.upper()

        if side is None:
            raise OperationalException("Order side is not set")

        if order_type is None:
            raise OperationalException("Order type is not set")

        if status is None:
            raise OperationalException("Status is not set")

        self.external_id = external_id
        self.price = parse_decimal_to_string(price)
        self.side = OrderSide.from_value(side).value
        self.order_type = OrderType.from_value(order_type).value
        self.status = OrderStatus.from_value(status).value
        self.position_id = position_id
        self.amount = parse_decimal_to_string(amount)
        self.net_gain = parse_decimal_to_string(net_gain)
        self.trade_closed_at = trade_closed_at
        self.trade_closed_price = trade_closed_price
        self.trade_closed_amount = trade_closed_amount
        self.created_at = created_at
        self.updated_at = updated_at
        self.filled_amount = parse_decimal_to_string(filled_amount)
        self.remaining_amount = parse_decimal_to_string(remaining_amount)
        self.cost = parse_decimal_to_string(cost)
        self.fee = fee

    def get_external_id(self):
        return self.external_id

    def get_target_symbol(self):
        return self.target_symbol

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_price(self):
        if self.price is not None:
            return parse_string_to_decimal(self.price)

        return 0

    def set_price(self, price):
        self.price = price

    def get_side(self):
        return self.side

    def get_status(self) -> OrderStatus:
        return self.status

    def set_status(self, status):
        self.status = OrderStatus.from_value(status).value

    def get_order_type(self):
        return self.order_type

    def get_amount(self):
        return parse_string_to_decimal(self.amount)

    def set_amount(self, amount):
        self.amount = amount

    def set_external_id(self, external_id):
        self.external_id = external_id

    def get_net_gain(self):
        return parse_string_to_decimal(self.net_gain)

    def set_net_gain(self, net_gain):
        self.net_gain = net_gain

    def get_trade_closed_at(self):
        return self.trade_closed_at

    def set_trade_closed_at(self, trade_closed_at):
        self.trade_closed_at = trade_closed_at

    def get_trade_closed_price(self):
        return parse_string_to_decimal(self.trade_closed_price)

    def set_trade_closed_price(self, trade_closed_price):
        self.trade_closed_price = trade_closed_price

    def get_trade_closed_amount(self):
        return parse_string_to_decimal(self.trade_closed_amount)

    def set_trade_closed_amount(self, trade_closed_amount):
        self.trade_closed_amount = trade_closed_amount

    def get_created_at(self):
        return self.created_at

    def set_created_at(self, created_at):
        self.created_at = created_at

    def get_updated_at(self):
        return self.updated_at

    def set_updated_at(self, updated_at):
        self.updated_at = updated_at

    def get_filled(self):

        if self.filled_amount is None:
            return parse_string_to_decimal('0')

        return parse_string_to_decimal(self.filled_amount)

    def set_filled(self, filled_amount):
        self.filled_amount = filled_amount

    def get_remaining(self):

        if self.remaining_amount is None:
            return parse_string_to_decimal('0')

        return parse_string_to_decimal(self.remaining_amount)

    def set_remaining(self, remaining_amount):
        self.remaining_amount = remaining_amount

    def get_cost(self):
        return parse_string_to_decimal(self.cost)

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
            "order_type": self.order_type,
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
            order_type=ccxt_order.get("type", None),
            side=ccxt_order.get("side", None),
            filled_amount=ccxt_order.get("filled", None),
            remaining_amount=ccxt_order.get("remaining", None),
            cost=ccxt_order.get("cost", None),
            fee=OrderFee.from_ccxt_fee(ccxt_order.get("fee", None)),
            created_at=datetime.strptime(ccxt_order.get("datetime", None), "%Y-%m-%dT%H:%M:%S.%fZ")
        )

    def update(self, data):

        if 'amount' in data and data['amount'] is not None:
            amount = data.pop('amount')
            self.amount = parse_decimal_to_string(amount)

        if 'price' in data and data['price'] is not None:
            price = data.pop('price')
            self.price = parse_decimal_to_string(price)

        if 'filled' in data and data['filled'] is not None:
            filled_amount = data.pop('filled')
            self.filled_amount = parse_decimal_to_string(filled_amount)

        if 'remaining' in data and data['remaining'] is not None:
            remaining_amount = data.pop('remaining')
            self.remaining_amount = parse_decimal_to_string(remaining_amount)

        if 'net_gain' in data and data['net_gain'] is not None:
            net_gain = data.pop('net_gain')
            self.net_gain = parse_decimal_to_string(net_gain)

        if 'trade_closed_price' in data and data['trade_closed_price'] is not None:
            trade_closed_price = data.pop('trade_closed_price')
            self.trade_closed_price = parse_decimal_to_string(trade_closed_price)

        if 'trade_closed_amount' in data and data['trade_closed_amount'] is not None:
            trade_closed_amount = data.pop('trade_closed_amount')
            self.trade_closed_amount = parse_decimal_to_string(trade_closed_amount)

        super().update(data)

    def __repr__(self):

        if not hasattr(self, "id"):
            id_value = "ccxt external order"
        else:
            id_value = self.id

        return self.repr(
            id=id_value,
            price=self.get_price(),
            amount=self.get_amount(),
            net_gain=self.get_net_gain(),
            external_id=self.external_id,
            status=self.status,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            side=self.side,
            order_type=self.order_type,
            filled_amount=self.get_filled(),
            remaining_amount=self.get_remaining(),
            cost=self.get_cost(),
        )
