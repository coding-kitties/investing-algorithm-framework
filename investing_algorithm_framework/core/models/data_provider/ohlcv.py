from investing_algorithm_framework.core.models.model_extension import \
    SQLAlchemyModelExtension


class OHLCV(SQLAlchemyModelExtension):

    def __init__(self, symbol, data):
        self.symbol = symbol
        self.target_symbol = symbol.split("/")[0]
        self.trading_symbol = symbol.split("/")[1]
        self.data = data

    def get_symbol(self):
        return self.symbol

    def get_target_symbol(self):
        return self.target_symbol

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_data(self):
        return self.data

    def to_dict(self):
        return {
            "symbol": self.get_symbol(),
            "data": self.get_data(),
        }

    @staticmethod
    def from_dict(data):
        return OHLCV(
            symbol=data.get("symbol"),
            data=data.get("data"),
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
            symbol=self.get_symbol(),
            data=self.get_data()
        )
