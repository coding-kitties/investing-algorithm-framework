from datetime import datetime
from investing_algorithm_framework.domain.constants import DATETIME_FORMAT

import pandas as pd


class OHLCV:
    COLUMNS = ["open", "high", "low", "close", "volume"]

    def __init__(self, symbol, data):
        self.symbol = symbol
        self.target_symbol = symbol.split("/")[0]
        self.trading_symbol = symbol.split("/")[1]
        self.data = []
        for row in data:
            self.data.append(
                [
                    row[0],
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    float(row[5])
                ]
            )

    def get_symbol(self):
        return self.symbol

    def get_target_symbol(self):
        return self.target_symbol

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_data(self):
        return self.data

    def to_dict(self, date_format=DATETIME_FORMAT):
        dict_data = {}

        for column in self.COLUMNS:
            dict_data[column] = []

        for row in self.get_data():
            date = datetime.strptime(row[0], date_format)
            date = date.strftime(date_format)
            dict_data["open"].append(date)
            dict_data["high"].append(row[1])
            dict_data["low"].append(row[2])
            dict_data["close"].append(row[3])
            dict_data["volume"].append(row[4])

        return dict_data

    def to_array(self, date_format=DATETIME_FORMAT):
        rows = []

        for row in self.get_data():
            datetime_object = datetime.strptime(
                row[0], DATETIME_FORMAT
            )
            rows.append([
                datetime_object.strftime(date_format),
                row[1],
                row[2],
                row[3],
                row[4],
                row[5]
            ])

        return rows

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

    def to_df(self):
        return pd.DataFrame(self.get_data(), columns=self.COLUMNS)
