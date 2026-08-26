from investing_algorithm_framework.domain.models.base_model import BaseModel


class PositionSnapshot(BaseModel):

    def __init__(
        self,
        symbol=None,
        amount=0,
        cost=0,
        portfolio_snapshot_id=None,
        long_amount=None,
        short_amount=None,
        long_cost=None,
        short_cost=None,
    ):
        self.symbol = symbol
        self.amount = amount
        self.cost = cost
        self.portfolio_snapshot_id = portfolio_snapshot_id
        self.long_amount = (
            max(amount, 0) if long_amount is None else long_amount
        )
        self.short_amount = (
            max(-amount, 0) if short_amount is None else short_amount
        )
        self.long_cost = (
            cost if long_cost is None and amount >= 0 else long_cost or 0
        )
        self.short_cost = (
            cost if short_cost is None and amount < 0 else short_cost or 0
        )

    def get_symbol(self):
        return self.symbol

    def set_symbol(self, symbol):
        self.symbol = symbol.upper()

    def get_amount(self):
        return self.amount

    def get_cost(self):
        return self.cost

    def set_cost(self, cost):
        self.cost = cost

    def set_amount(self, amount):
        self.amount = amount

    def get_portfolio_snapshot_id(self):
        return self.portfolio_snapshot_id

    @property
    def gross_amount(self):
        return self.long_amount + self.short_amount

    @property
    def net_cost(self):
        return self.long_cost - self.short_cost

    @property
    def gross_cost(self):
        return self.long_cost + self.short_cost

    def set_portfolio_snapshot_id(self, portfolio_snapshot_id):
        self.portfolio_snapshot_id = portfolio_snapshot_id

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "amount": self.amount,
            "cost": self.cost,
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "long_amount": self.long_amount,
            "short_amount": self.short_amount,
            "long_cost": self.long_cost,
            "short_cost": self.short_cost,
        }

    @staticmethod
    def from_dict(data):
        return PositionSnapshot(
            symbol=data.get("symbol"),
            amount=data.get("amount", 0),
            cost=data.get("cost", 0),
            portfolio_snapshot_id=data.get("portfolio_snapshot_id"),
            long_amount=data.get("long_amount"),
            short_amount=data.get("short_amount"),
            long_cost=data.get("long_cost"),
            short_cost=data.get("short_cost"),
        )

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            amount=self.amount,
            portfolio_snapshot_id=self.portfolio_snapshot_id,
        )
