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
    data_provider_identifier: str = None
    data_type: Union[DataType, str] = None
    symbol: str = None
    window_size: int = None
    time_frame: Union[TimeFrame, str] = None
    market: str = None
    storage_path: str = None
    pandas: bool = False
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

            object.__setattr__(
                self,
                'end_date',
                end_date.replace(tzinfo=timezone.utc)
            )

    def create_index_key(self):
        """
        Creates a unique index key for the data source based on its attributes.
        """
        # Get all attributes that are not None
        attributes = {
            key: value for key, value in self.__dict__.items() if value is not
            None
        }
        # Create a sorted tuple of the attributes to ensure consistent ordering
        sorted_attributes = tuple(sorted(attributes.items()))
        # Join the sorted attributes into a string to create a unique key
        return "_".join(f"{key}={value}" for key, value in sorted_attributes)

    def to_dict(self):
        """
        Converts the DataSource instance to a dictionary.
        """
        return {
            "data_provider_identifier": self.data_provider_identifier,
            "data_type": self.data_type.value if self.data_type else None,
            "symbol": self.symbol,
            "window_size": self.window_size,
            "time_frame": self.time_frame,
            "market": self.market,
            "storage_path": self.storage_path,
            "pandas": self.pandas,
            "save": self.save,
        }

    def __repr__(self):
        attributes = {
            key: value for key, value in self.__dict__.items() if value is not
            None
        }
        return (
            f"DataSource("
            f"{', '.join(f'{key}={value}' 
                         for key, value in attributes.items())
            })"
        )
