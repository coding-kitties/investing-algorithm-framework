from .models import TradingTimeFrame, TradingDataType, TimeUnit


class Strategy:

    def __init__(
        self,
        market=None,
        time_unit=None,
        interval=None,
        worker_id=None,
        symbols=None,
        limit=None,
        trading_data_type=None,
        trading_data_types=None,
        trading_time_frame=None,
    ):
        self._market = market
        self._time_unit = TimeUnit.from_value(time_unit).value
        self._interval = interval
        self._symbols = symbols
        self._limit = limit
        self._worker_id = worker_id

        if trading_data_type is not None:
            self._trading_data_type = TradingDataType \
                .from_value(trading_data_type)

        if trading_data_types is not None:
            trading_data_types = [TradingDataType.from_value(trading_data_type)
                                  for trading_data_type in trading_data_types]
            self._trading_data_types = trading_data_types

        if trading_time_frame is not None:
            self._trading_time_frame = TradingTimeFrame \
                .from_value(trading_time_frame)

    @property
    def market(self):
        return self._market

    @property
    def time_unit(self):
        return self._time_unit

    @property
    def interval(self):
        return self._interval

    @property
    def symbols(self):
        return self._symbols

    @property
    def limit(self):
        return self._limit

    @property
    def trading_data_type(self):
        return self._trading_data_type

    @property
    def trading_data_types(self):
        return self._trading_data_types

    @property
    def trading_time_frame(self):
        return self._trading_time_frame

    @property
    def worker_id(self):
        return self._worker_id
