from investing_algorithm_framework.domain.models.base_model import BaseModel


class Position(BaseModel):
    """
    This class represents a position in a portfolio.
    """

    def __init__(
        self,
        symbol=None,
        amount=0,
        cost=0,
        portfolio_id=None,
        long_amount=None,
        short_amount=None,
        long_cost=None,
        short_cost=None,
    ):
        self.symbol = symbol
        self.portfolio_id = portfolio_id
        if all(value is None for value in (
            long_amount, short_amount, long_cost, short_cost
        )):
            self._set_netting_values(amount, cost)
        else:
            self.long_amount = self._nonnegative(
                long_amount, "long_amount"
            )
            self.short_amount = self._nonnegative(
                short_amount, "short_amount"
            )
            self.long_cost = self._nonnegative(long_cost, "long_cost")
            self.short_cost = self._nonnegative(short_cost, "short_cost")

    @staticmethod
    def _nonnegative(value, name):
        value = 0 if value is None else value
        if value < 0:
            raise ValueError(f"{name} must be nonnegative")
        return value

    def _set_netting_values(self, amount, cost):
        cost = self._nonnegative(cost, "cost")
        if amount >= 0:
            self.long_amount = amount
            self.short_amount = 0
            self.long_cost = cost
            self.short_cost = 0
        else:
            self.long_amount = 0
            self.short_amount = abs(amount)
            self.long_cost = 0
            self.short_cost = cost

    def get_symbol(self):
        return self.symbol

    def set_symbol(self, symbol):
        self.symbol = symbol.upper()

    def get_amount(self):
        return self.amount

    def get_cost(self):
        return self.cost

    def set_cost(self, cost):
        cost = self._nonnegative(cost, "cost")
        if self.amount >= 0:
            self.long_cost = cost
            self.short_cost = 0
        else:
            self.long_cost = 0
            self.short_cost = cost

    def set_amount(self, amount):
        self._set_netting_values(amount, self.cost)

    @property
    def amount(self):
        return self.long_amount - self.short_amount

    @amount.setter
    def amount(self, amount):
        self.set_amount(amount)

    @property
    def cost(self):
        if self.amount > 0:
            return self.long_cost
        if self.amount < 0:
            return self.short_cost
        return 0

    @cost.setter
    def cost(self, cost):
        self.set_cost(cost)

    @property
    def gross_amount(self):
        return self.long_amount + self.short_amount

    @property
    def net_cost(self):
        return self.long_cost - self.short_cost

    @property
    def gross_cost(self):
        return self.long_cost + self.short_cost

    def get_portfolio_id(self):
        return self.portfolio_id

    def set_portfolio_id(self, portfolio_id):
        self.portfolio_id = portfolio_id

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "amount": self.amount,
            "cost": self.cost,
            "portfolio_id": self.portfolio_id,
            "long_amount": self.long_amount,
            "short_amount": self.short_amount,
            "long_cost": self.long_cost,
            "short_cost": self.short_cost,
        }

    @staticmethod
    def from_dict(data: dict):
        return Position(
            symbol=data.get("symbol"),
            amount=data.get("amount", 0),
            cost=data.get("cost", 0),
            portfolio_id=data.get("portfolio_id"),
            long_amount=data.get("long_amount"),
            short_amount=data.get("short_amount"),
            long_cost=data.get("long_cost"),
            short_cost=data.get("short_cost"),
        )

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            amount=self.amount,
            cost=self.cost,
            portfolio_id=self.portfolio_id,
            long_amount=self.long_amount,
            short_amount=self.short_amount,
            long_cost=self.long_cost,
            short_cost=self.short_cost,
        )
