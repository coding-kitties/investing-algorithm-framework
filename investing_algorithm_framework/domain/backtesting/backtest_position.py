from investing_algorithm_framework.domain.models.base_model import BaseModel


class BacktestPosition(BaseModel):

    def __init__(
        self,
        position,
        trading_symbol=False,
        amount_pending_buy=0.0,
        amount_pending_sell=0.0,
        total_value_portfolio=0.0
    ):
        self._symbol = position.symbol
        self._amount = position.amount + amount_pending_sell
        self._cost = position.cost
        self._price = 0.0
        self._trading_symbol = trading_symbol
        self._amount_pending_buy = amount_pending_buy
        self._amount_pending_sell = amount_pending_sell
        self._total_value_portfolio = total_value_portfolio

    @property
    def price(self):
        return self._price

    @price.setter
    def price(self, value):
        self._price = value

    @property
    def cost(self):

        if self._trading_symbol:
            return self.amount

        return self._cost

    @property
    def value(self):

        if self._trading_symbol:
            return self.amount

        return self._price * self.amount

    @property
    def growth(self):

        if self._amount == 0:
            return 0.0

        if self._trading_symbol:
            return 0.0

        return self.value - self.cost

    @property
    def growth_rate(self):

        if self._trading_symbol:
            return 0.0

        if self.cost == 0:
            return 0.0

        return self.growth / self.cost * 100

    @property
    def symbol(self):
        return self._symbol

    @property
    def amount(self):
        return self._amount

    @property
    def amount_pending_sell(self):
        return self._amount_pending_sell

    @amount_pending_sell.setter
    def amount_pending_sell(self, value):
        self._amount_pending_sell = value

    @property
    def amount_pending_buy(self):
        return self._amount_pending_buy

    @amount_pending_buy.setter
    def amount_pending_buy(self, value):
        self._amount_pending_buy = value

    @property
    def percentage_of_portfolio(self):

        if self._total_value_portfolio == 0:
            return 0.0

        return (self.value / self._total_value_portfolio) * 100

    def get_percentage_of_portfolio(self):

        if self._total_value_portfolio == 0:
            return 0.0

        return self.value / self._total_value_portfolio * 100

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "amount": self.amount,
            "cost": self.cost,
            "price": self.price,
            "value": self.value,
            "growth": self.growth,
            "growth_rate": self.growth_rate,
            "amount_pending_buy": self.amount_pending_buy,
            "amount_pending_sell": self.amount_pending_sell,
            "percentage_of_portfolio": self.percentage_of_portfolio
        }
