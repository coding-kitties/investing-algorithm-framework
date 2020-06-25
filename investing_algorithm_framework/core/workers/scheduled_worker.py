from abc import ABC

from investing_algorithm_framework.core.utils import TimeUnit
from investing_algorithm_framework.core.workers.worker import Worker


class ScheduledWorker(Worker, ABC):

    def get_time_unit(self) -> TimeUnit:
        assert getattr(self, 'time_unit', None) is not None, (
            "{} should either include a time_unit attribute, or override the "
            "`get_time_unit()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'time_unit')

    def get_time_interval(self) -> int:
        assert getattr(self, 'time_interval', None) is not None, (
            "{} should either include a time_interval attribute, or "
            "override the `get_time_interval()`, "
            "method.".format(self.__class__.__name__)
        )

        return getattr(self, 'time_interval')
