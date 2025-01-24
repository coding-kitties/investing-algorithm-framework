from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.order import OrderSide
from investing_algorithm_framework.domain.models.trade.trade_status import \
    TradeStatus


class Trade(BaseModel):
    """
    Trade model

    A trade is a combination of a buy and sell order that has been opened or
    closed.

    A trade is considered opened when a buy order is executed and there is
    no corresponding sell order. A trade is considered closed when a sell
    order is executed and the amount of the sell order is equal or larger
    to the amount of the buy order.

    A single sell order can close multiple buy orders. Also, a single
    buy order can be closed by multiple sell orders.

    Attributes:
        id (int): the id of the trade
        orders (List[Order]): the orders of the trade
        target_symbol (str): the target symbol of the trade
        trading_symbol (str): the trading symbol of the trade
        closed_at (datetime): the datetime when the trade was closed
        opened_at (datetime): the datetime when the trade was opened
        open_price (float): the open price of the trade
        amount (float): the amount of the trade
        remaining (float): the remaining amount of the trade
        net_gain (float): the net gain of the trade
        last_reported_price (float): the last reported price of the trade
        created_at (datetime): the datetime when the trade was created
        updated_at (datetime): the datetime when the trade was last updated
        status (str): the status of the trade
        stop_loss_percentage (float): the stop loss percentage of
            the trade
        trailing_stop_loss_percentage (float): the trailing stop
            loss percentage
    """

    def __init__(
        self,
        id,
        orders,
        target_symbol,
        trading_symbol,
        closed_at,
        opened_at,
        open_price,
        amount,
        cost,
        remaining,
        status,
        net_gain=0,
        last_reported_price=None,
        high_water_mark=None,
        updated_at=None,
        stop_loss_percentage=None,
        trailing_stop_loss_percentage=None,
        stop_loss_triggered=False,
    ):
        self.id = id
        self.orders = orders
        self.target_symbol = target_symbol
        self.trading_symbol = trading_symbol
        self.closed_at = closed_at
        self.opened_at = opened_at
        self.open_price = open_price
        self.amount = amount
        self.cost = cost
        self.remaining = remaining
        self.net_gain = net_gain
        self.last_reported_price = last_reported_price
        self.high_water_mark = high_water_mark
        self.status = status
        self.updated_at = updated_at
        self.stop_loss_percentage = stop_loss_percentage
        self.trailing_stop_loss_percentage = trailing_stop_loss_percentage
        self.stop_loss_triggered = stop_loss_triggered

    @property
    def closed_prices(self):
        return [
            order.price for order in self.orders
            if order.order_side == OrderSide.SELL.value
        ]

    @property
    def buy_order(self):

        if self.orders is None:
            return

        return [
            order for order in self.orders
            if order.order_side == OrderSide.BUY.value
        ][0]

    @property
    def symbol(self):
        return f"{self.target_symbol.upper()}/{self.trading_symbol.upper()}"

    @property
    def duration(self):
        if TradeStatus.CLOSED.equals(self.status):
            return self.closed_at - self.opened_at

        if self.opened_at is None:
            return None

        if self.updated_at is None:
            return None

        return self.updated_at - self.opened_at

    @property
    def size(self):
        return self.amount * self.open_price

    @property
    def change(self):
        if TradeStatus.CLOSED.equals(self.status):
            cost = self.amount * self.open_price
            return self.net_gain - cost

        if self.last_reported_price is None:
            return 0

        cost = self.remaining * self.open_price
        gain = (self.remaining * self.last_reported_price) - cost
        gain += self.net_gain
        return gain

    @property
    def net_gain_absolute(self):

        if TradeStatus.CLOSED.equals(self.status):
            return self.net_gain
        else:
            gain = 0

            if self.last_reported_price is not None:
                gain = (
                    self.remaining *
                    (self.last_reported_price - self.open_price)
                )

            gain += self.net_gain
            return gain

    @property
    def net_gain_percentage(self):

        if TradeStatus.CLOSED.equals(self.status):
            return (self.net_gain / self.cost) * 100

        else:
            gain = 0

            if self.last_reported_price is not None:
                gain = (
                    self.remaining *
                    (self.last_reported_price - self.open_price)
                )

            gain += self.net_gain

            if self.cost != 0:
                return (gain / self.cost) * 100

            return 0

    @property
    def percentage_change(self):

        if TradeStatus.CLOSED.equals(self.status):
            cost = self.amount * self.open_price
            gain = self.net_gain - cost
            return (gain / cost) * 100

        if self.last_reported_price is None:
            return 0

        cost = self.remaining * self.open_price
        gain = (self.remaining * self.last_reported_price) - cost
        gain += self.net_gain
        return (gain / cost) * 100

    def is_stop_loss_triggered(self):

        if self.stop_loss_percentage is None:
            return False

        if self.last_reported_price is None:
            return False

        if self.open_price is None:
            return False

        stop_loss_price = self.open_price * \
            (1 - (self.stop_loss_percentage / 100))

        return self.last_reported_price <= stop_loss_price

    def is_trailing_stop_loss_triggered(self):

        if self.trailing_stop_loss_percentage is None:
            return False

        if self.last_reported_price is None:
            return False

        if self.high_water_mark is None:

            if self.open_price is not None:
                self.high_water_mark = self.open_price
            else:
                return False

        stop_loss_price = self.high_water_mark * \
            (1 - (self.trailing_stop_loss_percentage / 100))

        return self.last_reported_price <= stop_loss_price

    def to_dict(self, datetime_format=None):

        if datetime_format is not None:
            opened_at = self.opened_at.strftime(datetime_format) \
                if self.opened_at else None
            closed_at = self.closed_at.strftime(datetime_format) \
                if self.closed_at else None
            updated_at = self.updated_at.strftime(datetime_format) \
                if self.updated_at else None
        else:
            opened_at = self.opened_at
            closed_at = self.closed_at
            updated_at = self.updated_at

        return {
            "id": self.id,
            "orders": [
                order.to_dict(datetime_format=datetime_format)
                for order in self.orders
            ],
            "target_symbol": self.target_symbol,
            "trading_symbol": self.trading_symbol,
            "status": self.status,
            "amount": self.amount,
            "remaining": self.remaining,
            "open_price": self.open_price,
            "last_reported_price": self.last_reported_price,
            "opened_at": opened_at,
            "closed_at": closed_at,
            "updated_at": updated_at,
            "net_gain": self.net_gain
        }

    @staticmethod
    def from_dict(data):
        return Trade(
            id=data.get("id", None),
            orders=data.get("orders", None),
            target_symbol=data["target_symbol"],
            trading_symbol=data["trading_symbol"],
            amount=data["amount"],
            open_price=data["open_price"],
            opened_at=data["opened_at"],
            closed_at=data["closed_at"],
            remaining=data.get("remaining", 0),
            net_gain=data.get("net_gain", 0),
            last_reported_price=data.get("last_reported_price"),
            status=data["status"],
            cost=data.get("cost", 0),
            updated_at=data.get("updated_at"),
        )

    def __repr__(self):
        return self.repr(
            id=self.id,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            status=self.status,
            amount=self.amount,
            remaining=self.remaining,
            open_price=self.open_price,
            opened_at=self.opened_at,
            closed_at=self.closed_at,
            net_gain=self.net_gain,
            last_reported_price=self.last_reported_price,
        )

    def __lt__(self, other):
        # Define the less-than comparison based on created_at attribute
        return self.opened_at < other.opened_at
