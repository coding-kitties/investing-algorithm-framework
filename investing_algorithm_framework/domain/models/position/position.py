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
        portfolio_id=None
    ):
        self.symbol = symbol
        self.amount = amount
        self.cost = cost
        self.portfolio_id = portfolio_id

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
        }

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            amount=self.amount,
            cost=self.cost,
            portfolio_id=self.portfolio_id,
        )
