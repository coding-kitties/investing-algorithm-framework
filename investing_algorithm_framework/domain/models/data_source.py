class DataSource:
    """
    Base class for data sources.
    """

    def __init__(
        self,
        data_type: str,
        symbol: str,
        market: str,
        time_frame: str,
        window_size: int,
        key: str, name: str
    ):
        self.name = name
        self.key = key
        self.data_type = data_type
        self.symbol = symbol
        self.market = market
        self.time_frame = time_frame
        self.window_size = window_size
