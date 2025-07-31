from .models import TimeUnit


class Strategy:

    def __init__(
        self,
        market=None,
        time_unit=None,
        interval=None,
        worker_id=None,
        symbols=None,
        limit=None,
    ):
        self._market = market
        self._time_unit = TimeUnit.from_value(time_unit).value
        self._interval = interval
        self._symbols = symbols
        self._limit = limit
        self._worker_id = worker_id

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
    def worker_id(self):
        return self._worker_id
