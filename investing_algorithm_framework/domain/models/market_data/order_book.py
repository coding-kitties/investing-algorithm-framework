from datetime import datetime
from typing import List


class OrderBook:

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

    @staticmethod
    def from_dict(data):
        return OrderBook(
            data.get("symbol"),
            data.get("bids"),
            data.get("asks"),
            data.get("creation_date")
        )

    def repr(self, **fields) -> str:
        """
        Helper for __repr__
        """

        field_strings = []
        at_least_one_attached_attribute = False

        for key, field in fields.items():
            field_strings.append(f'{key}={field!r}')
            at_least_one_attached_attribute = True

        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"

        return f"<{self.__class__.__name__} {id(self)}>"

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            bids=self.bids,
            asks=self.asks
        )
