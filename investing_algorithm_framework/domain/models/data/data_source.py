from dataclasses import dataclass
from .data_type import DataType

@dataclass(frozen=True)
class DataSource:
    """
    Base class for data sources.
    """
    data_provider_identifier: str = None
    data_type: DataType = None
    symbol: str = None
    window_size: int = None
    time_frame: str = None
    market: str = None
