from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.decimal_parsing import \
    parse_string_to_decimal


class Position(BaseModel):

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
        return parse_string_to_decimal(self.amount)

    def get_cost(self):
        return parse_string_to_decimal(self.cost)

    def set_cost(self, cost):
        self.cost = cost

    def set_amount(self, amount):
        self.amount = amount

    def get_portfolio_id(self):
        return self.portfolio_id

    def set_portfolio_id(self, portfolio_id):
        self.portfolio_id = portfolio_id

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            amount=self.amount,
            portfolio_id=self.portfolio_id,
        )
