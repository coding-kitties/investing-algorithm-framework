from investing_algorithm_framework.domain.models.base_model import BaseModel


class Position(BaseModel):

    def __init__(
        self,
        symbol=None,
        amount=0,
        portfolio_id=None
    ):
        self.symbol = symbol
        self.amount = amount
        self._cost = 0
        self.portfolio_id = portfolio_id

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            amount=self.amount,
            portfolio_id=self.portfolio_id,
            cost=self.cost
        )

    @property
    def cost(self):
        return self._cost

    @cost.setter
    def cost(self, value):
        self._cost = value
