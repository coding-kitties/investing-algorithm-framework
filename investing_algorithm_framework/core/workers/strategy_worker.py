from flask_apscheduler import APScheduler

from investing_algorithm_framework.core.models import TimeUnit, db
from investing_algorithm_framework.core.models.data_provider import \
    TradingDataTypes
from investing_algorithm_framework.utils import random_string


class StrategyWorker:

    def __init__(
            self,
            decorated,
            worker_id,
            time_unit,
            interval,
            data_provider_identifier,
            trading_data_type,
            trading_data_types,
            target_symbol,
            target_symbols,
            trading_symbol
    ):
        self.data_provider_identifier = data_provider_identifier
        self.trading_data_type = trading_data_type
        self.trading_data_types = trading_data_types
        self.target_symbol = target_symbol
        self.target_symbols = target_symbols
        self.trading_symbol = trading_symbol

        from investing_algorithm_framework.core.context import algorithm

        self.decorated = decorated
        self.worker_id = worker_id

        if self.worker_id is None:
            self.worker_id = self.decorated.__name__

            if self.decorated.__name__ in algorithm.workers:
                self.id = random_string(10)

        if isinstance(time_unit, TimeUnit):
            self.time_unit = time_unit.value
        else:
            self.time_unit = TimeUnit.from_string(time_unit).value

        self.interval = interval
        algorithm.add_strategy(self)

    def add_to_scheduler(self, app_scheduler: APScheduler):
        if TimeUnit.SECONDS.equals(self.time_unit):
            app_scheduler.add_job(
                id=self.worker_id,
                name=self.worker_id,
                func=self.__call__,
                trigger="interval",
                seconds=self.interval
            )
        elif TimeUnit.MINUTE.equals(self.time_unit):
            app_scheduler.add_job(
                id=self.worker_id,
                name=self.worker_id,
                func=self.__call__,
                trigger="interval",
                minutes=self.interval
            )
        elif TimeUnit.HOUR.equals(self.time_unit):
            app_scheduler.add_job(
                id=self.worker_id,
                name=self.worker_id,
                func=self.__call__,
                trigger="interval",
                minutes=(self.interval * 60)
            )

    def __call__(
            self,
            time_unit: TimeUnit = TimeUnit.MINUTE.value,
            interval=10,
            data_provider_identifier=None,
            trading_data_type=None,
            trading_data_types=None,
            target_symbol=None,
            target_symbols=None,
            trading_symbol=None
    ):
        from investing_algorithm_framework.core.context import algorithm

        data = None

        if self.data_provider_identifier is not None:

            if self.trading_data_types is not None:

                data = {}

                for trading_data_type in self.trading_data_types:

                    if isinstance(trading_data_type, str):
                        trading_data_type = TradingDataTypes\
                            .from_string(trading_data_type)

                    data[trading_data_type.value] = algorithm.get_data(
                        self.data_provider_identifier,
                        trading_data_type,
                        target_symbols=self.target_symbols,
                        target_symbol=self.target_symbol,
                        trading_symbol=self.trading_symbol
                    )
            else:
                data = algorithm.get_data(
                    self.data_provider_identifier,
                    self.trading_data_type,
                    target_symbols=self.target_symbols,
                    target_symbol=self.target_symbol,
                    trading_symbol=self.trading_symbol
                )

        # Run the decorated function in app context
        with db.app.app_context():
            self.decorated(algorithm, data)
