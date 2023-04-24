from datetime import datetime


class Ticker:

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

    @staticmethod
    def from_dict(data):
        return Ticker(
            symbol=data.get("symbol"),
            price=data.get("price"),
            ask_price=data.get("ask_price"),
            ask_volume=data.get("ask_volume"),
            bid_price=data.get("bid_price"),
            bid_volume=data.get("bid_volume"),
            high_price=data.get("high_price"),
            low_price=data.get("low_price"),
            creation_date=data.get("creation_date")
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
            price=self.price,
            ask_price=self.ask_price,
            ask_volume=self.ask_volume,
            bid_price=self.bid_price,
            bid_volume=self.bid_volume,
            high_price=self.high_price,
            low_price=self.low_price
        )
