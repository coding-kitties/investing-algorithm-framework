from investing_algorithm_framework.domain.decimal_parsing import\
    parse_string_to_decimal
from investing_algorithm_framework.domain.models.base_model import BaseModel


class PositionCost(BaseModel):

    def __init__(
        self,
        symbol=None,
        amount=0,
        position_id=None,
        created_at=None,
    ):
        self.symbol = symbol
        self.amount = amount
        self.position_id = position_id
        self.created_at = created_at

    def get_symbol(self):
        return self.symbol

    def set_symbol(self, symbol):
        self.symbol = symbol.upper()

    def get_amount(self):
        return parse_string_to_decimal(self.amount)

    def set_amount(self, amount):
        self.amount = amount

    def get_position_id(self):
        return self.position_id

    def set_position_id(self, position_id):
        self.position_id = position_id

    def get_price(self):
        return parse_string_to_decimal(self.price)

    def set_price(self, price):
        self.price = price

    def get_created_at(self):
        return self.created_at

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            amount=self.amount,
            position_id=self.position_id,
            created_at=self.created_at,
        )
