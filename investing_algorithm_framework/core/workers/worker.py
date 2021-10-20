from flask_apscheduler import APScheduler

from investing_algorithm_framework.core.models import TimeUnit
from investing_algorithm_framework.utils import random_string
from investing_algorithm_framework.core.models import db


class Worker:

    def __init__(self, decorated, worker_id, time_unit, interval):
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
        algorithm.add_worker(self)

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
            interval=10
    ):
        from investing_algorithm_framework.core.context import algorithm

        # Run the decorated function in app context
        with db.app.app_context():
            self.decorated(algorithm)
