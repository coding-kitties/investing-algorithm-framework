from datetime import datetime

from investing_algorithm_framework.core.models.model_extension import \
    ModelExtension


class Ticker(ModelExtension):

    def __init__(
            self,
            symbol,
            price,
            ask_price=None,
            ask_volume=None,
            bid_price=None,
            bid_volume=None,
            high_price=None,
            low_price=None,
            creation_date=None
    ):
        self.symbol = symbol
        self.price = price
        self.ask_price = ask_price
        self.ask_volume = ask_volume
        self.bid_price = bid_price
        self.bid_volume = bid_volume
        self.high_price = high_price
        self.low_price = low_price

        if creation_date is None:
            self.creation_date = datetime.now()

    def get_price(self):
        return self.price

    def get_creation_date(self):
        return self.creation_date

    def get_symbol(self):
        return self.symbol

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "price": self.price,
            "ask_price": self.ask_price,
            "ask_volume": self.ask_volume,
            "bid_price": self.bid_price,
            "bid_volume": self.bid_volume,
            "high_price": self.high_price,
            "low_price": self.low_price
        }

    def __repr__(self):
        return self.repr(
            symbol=self.symbol,
            price=self.price,
            ask_price=self.ask_price,
            ask_volume=self.ask_volume,
            bid_price=self.bid_price,
            bid_volume=self.bid_volume,
            high_price=self.high_price,
            low_price=self.low_price
        )
