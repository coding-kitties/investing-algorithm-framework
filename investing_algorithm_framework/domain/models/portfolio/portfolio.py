from investing_algorithm_framework.domain.models.base_model import BaseModel


class Portfolio(BaseModel):

    def __init__(self, identifier, trading_symbol):
        self.identifier = identifier
        self.updated_at = None
        self.trading_symbol = trading_symbol.upper()

    def __repr__(self):
        return self.repr(
            identifier=self.identifier, trading_symbol=self.trading_symbol,
        )
