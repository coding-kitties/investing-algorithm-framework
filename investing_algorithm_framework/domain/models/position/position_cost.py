from investing_algorithm_framework.domain.models.base_model import BaseModel


class PositionCost(BaseModel):

    def __init__(
        self,
        symbol=None,
        amount=0,
        position_id=None
    ):
        self.symbol = symbol
        self.amount = amount
        self.position_id = position_id

    def get_symbol(self):
        return self.symbol

    def set_symbol(self, symbol):
        self.symbol = symbol.upper()

    def get_amount(self):
        return self.amount

    def set_amount(self, amount):
        self.amount = amount

    def get_position_id(self):
        return self.position_id

    def set_position_id(self, position_id):
        self.position_id = position_id

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            amount=self.amount,
            position_id=self.position_id,
        )
