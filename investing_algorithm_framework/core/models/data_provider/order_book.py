from datetime import datetime
from typing import List

from investing_algorithm_framework.core.models.model_extension import \
    ModelExtension


class OrderBook(ModelExtension):

    def __init__(self, symbol, bids: List, asks: List, creation_date=None):
        self.symbol = symbol
        self.bids = bids
        self.asks = asks

        if creation_date is None:
            self.creation_date = datetime.now()

    def get_bids(self):
        return self.bids

    def get_asks(self):
        return self.asks

    def get_symbol(self):
        return self.symbol

    def to_dict(self):

        return {
            "symbol": self.symbol,
            "bids": self.bids,
            "asks": self.asks
        }

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            bids=self.bids,
            asks=self.asks
        )
