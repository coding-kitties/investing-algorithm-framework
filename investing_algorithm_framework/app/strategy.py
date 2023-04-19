from typing import List
from investing_algorithm_framework.domain import \
    TimeUnit, TradingTimeFrame, TradingDataType


class TradingStrategy:
    symbols: List[str] = []
    time_unit: str = None
    interval: int = None
    market: str = None
    trading_data_type = None
    trading_data_types: list = None
    trading_time_frame = None
    trading_time_frame_start_date = None
    worker_id: str = None
    decorated = None

    def __init__(
        self,
        time_unit=None,
        interval=None,
        market=None,
        symbols=None,
        trading_data_type=None,
        trading_data_types=None,
        trading_time_frame=None,
        trading_time_frame_start_date=None,
        worker_id=None,
        decorated=None
    ):

        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if interval is not None:
            self.interval = interval

        if market is not None:
            self.market = market

        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if symbols is not None:
            self.symbols = symbols

        if trading_time_frame_start_date is not None:
            self.trading_time_frame_start_date = trading_time_frame_start_date

        if trading_data_type is not None:
            self.trading_data_types = [
                TradingDataType.from_value(trading_data_type)
            ]

        if trading_data_types is not None:
            self.trading_data_types = [
                TradingDataType.from_value(trading_data_type)
                for trading_data_type in trading_data_types
            ]

        if trading_time_frame is not None:
            self.trading_time_frame = TradingTimeFrame\
                .from_value(trading_time_frame)

        if decorated is not None:
            self.decorated = decorated

        if worker_id is not None:
            self.worker_id = worker_id
        elif self.decorated:
            self.worker_id = decorated.__name__
        else:
            self.worker_id = self.__class__.__name__

    def run_strategy(self, market_data, algorithm):
        self.apply_strategy(algorithm=algorithm, market_data=market_data)

    def apply_strategy(
        self,
        algorithm,
        market_data,
    ):
        if self.decorated:
            self.decorated(algorithm=algorithm, market_data=market_data)
        else:
            raise NotImplementedError("Apply strategy is not implemented")
