from datetime import datetime
from investing_algorithm_framework.domain.models.base_model import BaseModel


class Trade(BaseModel):

    def __init__(
        self,
        buy_order_id,
        target_symbol,
        trading_symbol,
        amount,
        open_price,
        opened_at,
        closed_price=None,
        closed_at=None,
        current_price=None,
        sell_order_id=None,
    ):
        self._target_symbol = target_symbol
        self._trading_symbol = trading_symbol
        self._amount = amount
        self._open_price = open_price
        self._closed_price = closed_price
        self._closed_at = closed_at
        self._opened_at = opened_at
        self._trading_symbol = trading_symbol
        self._current_price = current_price
        self._buy_order_id = buy_order_id
        self._sell_order_id = sell_order_id,

    @property
    def buy_order_id(self):
        return self._buy_order_id

    @property
    def sell_order_id(self):
        return self._sell_order_id

    @property
    def target_symbol(self):
        return self._target_symbol

    @property
    def trading_symbol(self):
        return self._trading_symbol

    @property
    def amount(self):
        return self._amount

    @property
    def open_price(self):
        return self._open_price

    @property
    def closed_price(self):
        return self._closed_price

    @property
    def closed_at(self):
        return self._closed_at

    @property
    def opened_at(self):
        return self._opened_at

    @property
    def size(self):
        return self.amount * self.open_price

    @property
    def net_gain(self):

        if self.closed_at is None:
            return 0

        return self.amount * (self.closed_price - self.open_price)

    @property
    def net_gain_percentage(self):

        if self.closed_at is None:
            return 0

        return self.net_gain / self.size * 100

    @property
    def duration(self):
        closed_at = self.closed_at

        if closed_at is None:
            closed_at = datetime.utcnow()

        return (closed_at - self.opened_at).total_seconds() / 3600

    @property
    def current_price(self):
        return self._current_price

    @current_price.setter
    def current_price(self, current_price):
        self._current_price = current_price

    @property
    def value(self):

        if self.current_price is None:
            return None

        return self.amount * self.current_price

    @property
    def percentage_change(self):

        if self.closed_at is not None or self.value is None:
            return 0
        value = self.value
        return (value - self.size) / self.size * 100

    def get_percentage_change(self):
        return self.percentage_change

    @property
    def absolute_change(self):

        if self.closed_at is None:
            return 0

        value = self.value
        return value - self.size

    def get_absolute_change(self):
        return self.absolute_change

    def is_manual_stop_loss_trigger(
        self, current_price, prices, stop_loss_percentage
    ):
        # Stop loss is triggered when the current price is lower than the
        # calculated stop loss price. The stop loss price is calculated by
        # taking the highest price of the given range. If the highest price
        # is lower than the open price, the stop loss price is calculated by
        # taking the open price and subtracting the stop loss percentage.
        # If the highest price is higher than the open price, the stop loss
        # price is calculated by taking the open price and adding the stop
        # loss percentage.

        if current_price < self.open_price:
            stop_loss_price = self.open_price * \
                              (1 - stop_loss_percentage / 100)
            return current_price <= stop_loss_price
        else:
            highest_price = max(prices)
            stop_loss_price = highest_price * (1 - stop_loss_percentage / 100)
            return current_price <= stop_loss_price

    def __repr__(self):
        return self.repr(
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            amount=self.amount,
            open_price=self.open_price,
            closed_price=self.closed_price,
            opened_at=self.opened_at,
            closed_at=self.closed_at,
            current_price=self.current_price,
            value=self.value,
            change=self.percentage_change,
            absolute_change=self.absolute_change,
        )
