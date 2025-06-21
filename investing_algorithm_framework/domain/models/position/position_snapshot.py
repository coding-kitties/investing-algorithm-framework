from investing_algorithm_framework.domain.models.base_model import BaseModel


class PositionSnapshot(BaseModel):

    def __init__(
        self,
        id=None,
        symbol=None,
        amount=0,
        cost=0,
        portfolio_snapshot_id=None
    ):
        self.id = id
        self.symbol = symbol
        self.amount = amount
        self.cost = cost
        self.portfolio_snapshot_id = portfolio_snapshot_id

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

    def set_portfolio_snapshot_id(self, portfolio_snapshot_id):
        self.portfolio_snapshot_id = portfolio_snapshot_id

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            amount=self.amount,
            portfolio_snapshot_id=self.portfolio_snapshot_id,
        )

    @staticmethod
    def get_column_names():
        return [
            "id",
            "symbol",
            "amount",
            "cost",
            "portfolio_snapshot_id",
        ]
    
    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "amount": self.amount,
            "cost": self.cost,
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
        }