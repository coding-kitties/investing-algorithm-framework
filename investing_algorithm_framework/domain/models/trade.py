from investing_algorithm_framework.domain.models.base_model import BaseModel


class Trade(BaseModel):

    def __init__(
        self,
        target_symbol,
        trading_symbol,
        amount,
        open_price,
        closed_price,
        closed_at,
        opened_at
    ):
        self._target_symbol = target_symbol
        self._trading_symbol = trading_symbol
        self._amount = amount
        self._open_price = open_price
        self._closed_price = closed_price
        self._closed_at = closed_at
        self._opened_at = opened_at
        self._trading_symbol = trading_symbol

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
        return self.amount * (self.closed_price - self.open_price)

    @property
    def net_gain_percentage(self):
        return self.net_gain / self.size * 100

    @property
    def duration(self):
        return (self.closed_at - self.opened_at).total_seconds() / 3600

    def __repr__(self):
        return self.repr(
            target_symbol=self.target_symbol,
            trading_symbol=self.trading_symbol,
            amount=self.amount,
            open_price=self.open_price,
            closed_price=self.closed_price,
            opened_at=self.opened_at,
            closed_at=self.closed_at,
        )
