from dateutil.parser import parse

from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.order import OrderSide, Order
from investing_algorithm_framework.domain.models.trade.trade_status import \
    TradeStatus
from investing_algorithm_framework.domain.models.trade.trade_stop_loss import \
    TradeStopLoss
from investing_algorithm_framework.domain.models.trade\
    .trade_take_profit import TradeTakeProfit


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
        orders: str, the id of the buy order
        target_symbol: str, the target symbol of the trade
        trading_symbol: str, the trading symbol of the trade
        closed_at: datetime, the datetime when the trade was closed
        amount: float, the amount of the trade
        available_amount: float, the available amount of the trade
        remaining: float, the remaining amount that is not filled by the
            buy order that opened the trade.
        filled_amount: float, the filled amount of the trade by the buy
            order that opened the trade.
        net_gain: float, the net gain of the trade
        last_reported_price: float, the last reported price of the trade
        last_reported_price_datetime: datetime, the datetime when the last
            reported price was reported
        created_at: datetime, the datetime when the trade was created
        updated_at: datetime, the datetime when the trade was last updated
        status: str, the status of the trade
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
        available_amount,
        cost,
        remaining,
        filled_amount,
        status,
        net_gain=0,
        last_reported_price=None,
        last_reported_price_datetime=None,
        high_water_mark=None,
        high_water_mark_datetime=None,
        updated_at=None,
        stop_losses=None,
        take_profits=None,
    ):
        self.id = id
        self.orders = orders
        self.target_symbol = target_symbol
        self.trading_symbol = trading_symbol
        self.closed_at = closed_at
        self.opened_at = opened_at
        self.open_price = open_price
        self.amount = amount
        self.available_amount = available_amount
        self.cost = cost
        self.remaining = remaining
        self.filled_amount = filled_amount
        self.net_gain = net_gain
        self.last_reported_price = last_reported_price
        self.last_reported_price_datetime = last_reported_price_datetime
        self.high_water_mark = high_water_mark
        self.high_water_mark_datetime = high_water_mark_datetime
        self.status = status
        self.updated_at = updated_at
        self.stop_losses = stop_losses
        self.take_profits = take_profits

    def update(self, data):

        if "status" in data:
            self.status = TradeStatus.from_value(data["status"])

            if TradeStatus.CLOSED.equals(self.status):

                # Set all stop losses to inactive
                if self.stop_losses is not None:
                    for stop_loss in self.stop_losses:
                        stop_loss.active = False

                # set all take profits to inactive
                if self.take_profits is not None:
                    for take_profit in self.take_profits:
                        take_profit.active = False

        if "last_reported_price" in data:
            self.last_reported_price = data["last_reported_price"]

            if self.high_water_mark is None:
                self.high_water_mark = data["last_reported_price"]
                self.high_water_mark_datetime = \
                    data["last_reported_price_datetime"]
            else:

                if data["last_reported_price"] > self.high_water_mark:
                    self.high_water_mark = data["last_reported_price"]
                    self.high_water_mark_datetime = \
                        data["last_reported_price_datetime"]

        return super().update(data)

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
            # Get the total hours between the closed and opened datetime
            diff = self.closed_at - self.opened_at
            return diff.total_seconds() / 3600

        if self.opened_at is None:
            return None

        if self.updated_at is None:
            return None

        diff = self.updated_at - self.opened_at
        return diff.total_seconds() / 3600

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

            if self.cost != 0:
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

    def is_take_profit_triggered(self):

        if self.take_profit_percentage is None:
            return False

        if self.last_reported_price is None:
            return False

        if self.open_price is None:
            return False

        take_profit_price = self.open_price * \
            (1 + (self.take_profit_percentage / 100))

        return self.last_reported_price >= take_profit_price

    def is_trailing_take_profit_triggered(self):
        """
        Function to check if the trailing take profit is triggered.
        The trailing take profit is triggered when the last reported price
        is greater than or equal to the high water mark times the trailing
        take profit percentage.
        """

        if self.trailing_take_profit_percentage is None:
            return False

        if self.last_reported_price is None:
            return False

        if self.high_water_mark is None:

            if self.open_price is not None:
                self.high_water_mark = self.open_price
            else:
                return False

        take_profit_price = self.high_water_mark * \
            (1 + (self.trailing_take_profit_percentage / 100))

        return self.last_reported_price >= take_profit_price

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
            "net_gain": self.net_gain,
            "cost": self.cost,
            "stop_losses": [
                stop_loss.to_dict(datetime_format=datetime_format)
                for stop_loss in self.stop_losses
            ] if self.stop_losses else None,
            "take_profits": [
                take_profit.to_dict(datetime_format=datetime_format)
                for take_profit in self.take_profits
            ] if self.take_profits else None,
        }

    @staticmethod
    def from_dict(data):
        opened_at = None
        closed_at = None
        updated_at = None
        stop_losses = None
        take_profits = None
        orders = None

        if "opened_at" in data and data["opened_at"] is not None:
            opened_at = parse(data["opened_at"])

        if "closed_at" in data and data["closed_at"] is not None:
            closed_at = parse(data["closed_at"])

        if "updated_at" in data and data["updated_at"] is not None:
            updated_at = parse(data["updated_at"])

        if "stop_losses" in data and data["stop_losses"] is not None:
            stop_losses = [
                TradeStopLoss.from_dict(stop_loss)
                for stop_loss in data["stop_losses"]
            ]

        if "take_profits" in data and data["take_profits"] is not None:
            take_profits = [
                TradeTakeProfit.from_dict(take_profit)
                for take_profit in data["take_profits"]
            ]

        if "orders" in data and data["orders"] is not None:
            orders = [
                Order.from_dict(order)
                for order in data["orders"]
            ]

        return Trade(
            id=data.get("id", None),
            orders=orders,
            target_symbol=data["target_symbol"],
            trading_symbol=data["trading_symbol"],
            amount=data["amount"],
            open_price=data["open_price"],
            opened_at=opened_at,
            closed_at=closed_at,
            filled_amount=data.get("filled_amount", 0),
            available_amount=data.get("available_amount", 0),
            remaining=data.get("remaining", 0),
            net_gain=data.get("net_gain", 0),
            last_reported_price=data.get("last_reported_price"),
            status=data["status"],
            cost=data.get("cost", 0),
            updated_at=updated_at,
            stop_losses=stop_losses,
            take_profits=take_profits,
        )

    def __repr__(self):
        return self.repr(
            id=self.id,
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            status=self.status,
            amount=self.amount,
            available_amount=self.available_amount,
            filled_amount=self.filled_amount,
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
