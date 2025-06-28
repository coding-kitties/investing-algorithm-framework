from dataclasses import dataclass
from .data_type import DataType

@dataclass()
class DataSource:
    """
    Base class for data sources.
    """
    identifier: str = None
    data_type: DataType = None
    symbol: str = None
    window_size: int = None
    time_frame: str = None
