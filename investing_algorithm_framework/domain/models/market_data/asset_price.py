from datetime import datetime


class AssetPrice:

    def __init__(self, symbol, price, datetime):
        self.symbol = symbol
        self.price = price
        self.datetime = datetime

    def get_symbol(self):
        return self.symbol

    def get_price(self):

        if self.price is None:
            return 0

        return self.price

    def get_datetime(self):

        if self.datetime is None:
            return datetime.utcnow()

        return self.datetime

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
            symbol=self.get_symbol(),
            price=self.price,
            datetime=self.datetime
        )
