from dataclasses import dataclass
from typing import Union
from datetime import datetime, timezone
from dateutil import parser
from .data_type import DataType
from investing_algorithm_framework.domain.models.time_frame import TimeFrame


@dataclass(frozen=True)
class DataSource:
    """
    Base class for data sources.
    """
    identifier: str = None
    data_provider_identifier: str = None
    data_type: Union[DataType, str] = None
    symbol: str = None
    window_size: int = None
    time_frame: Union[TimeFrame, str] = None
    market: str = None
    storage_path: str = None
    pandas: bool = False
    date: Union[datetime, None] = None
    start_date: Union[datetime, None] = None
    end_date: Union[datetime, None] = None
    save: bool = False

    def __post_init__(self):
        # Convert data_type and time_frame to their respective enums if needed
        if isinstance(self.data_type, str):
            object.__setattr__(self, 'data_type',
                               DataType.from_string(self.data_type))

        if isinstance(self.time_frame, str):
            object.__setattr__(self, 'time_frame',
                               TimeFrame.from_string(self.time_frame))

        start_date = self.start_date
        end_date = self.end_date

        # Parse the start_date if it is a string and
        # make sure its set to timezone utc
        if start_date is None:

            if isinstance(self.start_date, str):
                start_date = parser.parse(start_date)

            if start_date is not None:
                object.__setattr__(
                    self,
                    'start_date',
                    start_date.replace(tzinfo=timezone.utc)
                )

        # Parse the end_date if it is a string and
        # make sure its set to timezone utc
        if end_date is None:

            if isinstance(self.end_date, str):
                end_date = parser.parse(end_date)

            if end_date is not None:
                object.__setattr__(
                    self,
                    'end_date',
                    end_date.replace(tzinfo=timezone.utc)
                )

        if self.market is not None:
            object.__setattr__(self, 'market', self.market.upper())

        if self.symbol is not None:
            object.__setattr__(self, 'symbol', self.symbol.upper())

    def get_identifier(self):
        """
        Returns the identifier or creates a unique identifier for the
        data source based on its attributes.
        """

        if self.identifier is not None:
            return self.identifier

        if DataType.OHLCV.equals(self.data_type):
            return (f"{self.data_type.value}_{self.market}_"
                    f"{self.symbol}_{self.time_frame.value}")

        elif DataType.CUSTOM.equals(self.data_type):
            identifier = "CUSTOM"

            if self.symbol is not None:
                identifier += f"_{self.symbol}"

            if self.time_frame is not None:
                identifier += f"_{self.time_frame.value}"

            if self.market is not None:
                identifier += f"_{self.market}"

            if self.window_size is not None:
                identifier += f"_{self.window_size}"

            return identifier

    def to_dict(self):
        """
        Converts the DataSource instance to a dictionary.
        """
        non_null_attributes = {
            key: value for key, value in self.__dict__.items()
            if value is not None
        }
        # Convert DataType and TimeFrame to their string representations
        if self.data_type is not None:
            non_null_attributes['data_type'] = self.data_type.value
        if self.time_frame is not None:
            non_null_attributes['time_frame'] = self.time_frame.value

        return non_null_attributes

    def __repr__(self):
        return (
            f"DataSource(identifier={self.identifier}, "
            f"data_provider_identifier={self.data_provider_identifier}, "
            f"data_type={self.data_type}, symbol={self.symbol}, "
            f"window_size={self.window_size}, time_frame={self.time_frame}, "
            f"market={self.market}, storage_path={self.storage_path}, "
            f"pandas={self.pandas}, date={self.date}, "
            f"start_date={self.start_date}, end_date={self.end_date}, "
            f"save={self.save})"
        )

    def __eq__(self, other):
        """
        Compares two DataSource instances for equality.

        OHLCV data sources are considered equal if they have:
        - The same data_type (OHLCV), symbol, time_frame, and market.
        - If no market and timeframe is specified, then
            they are considered equal for the same symbol
            and data_type.
        """
        if DataType.OHLCV.equals(self.data_type):

            if other.time_frame is None and other.window_size is None:
                return (self.data_type == other.data_type and
                        self.symbol == other.symbol)
            elif self.time_frame is None and self.window_size is None:
                return (self.data_type == other.data_type and
                        self.symbol == other.symbol)

            return (self.time_frame == other.time_frame and
                    self.market == other.market and
                    self.symbol == other.symbol and
                    self.data_type == other.data_type)

        elif DataType.CUSTOM.equals(self.data_type):
            return (self.data_type == other.data_type and
                    self.symbol == other.symbol and
                    self.window_size == other.window_size and
                    self.time_frame == other.time_frame and
                    self.market == other.market)

        elif DataType.TICKER.equals(self.data_type):
            return (self.data_type == other.data_type and
                    self.symbol == other.symbol and
                    self.market == other.market)

        return False
