from abc import ABC
from datetime import datetime
from typing import Dict, Any

from investing_algorithm_framework.core.utils import TimeUnit
from investing_algorithm_framework.core.workers.worker import Worker


class ScheduledWorker(Worker, ABC):
    time_unit: TimeUnit = None
    time_interval: int = None

    def start(self, **kwargs: Dict[str, Any]) -> None:

        # If the worker has never run, run it
        if self.last_run is None:
            super(ScheduledWorker, self).start(**kwargs)

        else:
            # Get the current time
            elapsed_time = datetime.now() - self.last_run

            # Second evaluation
            if self.get_time_unit() is TimeUnit.SECOND:
                seconds = elapsed_time.total_seconds()

                if seconds > self.get_time_interval():
                    super(ScheduledWorker, self).start(**kwargs)

            # Minute evaluation
            elif self.get_time_unit() is TimeUnit.MINUTE:
                minutes = divmod(elapsed_time.total_seconds(), 60)

                if minutes > self.get_time_interval():
                    super(ScheduledWorker, self).start(**kwargs)

            # Hour evaluation
            elif self.get_time_unit() is TimeUnit.HOUR:
                hours = divmod(elapsed_time.total_seconds(), 3600)

                if hours > self.get_time_interval():
                    super(ScheduledWorker, self).start(**kwargs)

    def get_time_unit(self) -> TimeUnit:
        assert getattr(self, 'time_unit', None) is not None, (
            "{} should either include a time_unit attribute, or override the "
            "`get_time_unit()` method.".format(self.__class__.__name__)
        )

        time_unit = getattr(self, 'time_unit')

        if isinstance(time_unit, TimeUnit):
            return time_unit
        else:
            return TimeUnit.from_string(time_unit)

    def get_time_interval(self) -> int:
        assert getattr(self, 'time_interval', None) is not None, (
            "{} should either include a time_interval attribute, or override "
            "the `get_time_interval()` method.".format(self.__class__.__name__)
        )

        return getattr(self, 'time_interval')
