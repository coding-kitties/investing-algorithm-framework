from datetime import datetime
from collections import namedtuple
from typing import Dict, List

from investing_algorithm_framework.core.utils import TimeUnit
from investing_algorithm_framework.core.exceptions import OperationalException

ExecutionTask = namedtuple('ExecutionTask', 'time_unit interval last_run')


class ExecutionScheduler:
    """
    Class ExecutionScheduler: This is a lazy scheduler. It only runs it's
    scheduling algorithm when it is asked to.It will then evaluate all the
    time units and intervals and decide which executions it needs to return.

    At the initial run, it will schedule all the executions.
    """

    def __init__(self):
        self._planning: Dict[str, ExecutionTask] = {}

    def add_execution_task(
            self,
            execution_id: str,
            time_unit: TimeUnit,
            interval: int = None
    ) -> None:
        """
        Function that will add an appointment to the scheduler
        """

        if execution_id not in self._planning:

            if time_unit is not TimeUnit.ALWAYS:

                if interval is None:
                    raise OperationalException(
                        "Appoint must set an interval with the "
                        "corresponding time unit"
                    )
                elif interval < 1:
                    raise OperationalException(
                        "Interval for task time unit is smaller then 1"
                    )

            self._planning[execution_id] = ExecutionTask(
                time_unit=time_unit, interval=interval, last_run=None
            )

        else:
            raise OperationalException(
                "Can't add execution task, execution id is already taken"
            )

    def schedule_executions(self) -> List[str]:
        """
        Function that will return all appointments that have hit their time
        threshold
        """

        appointments: List[str] = []

        for appointment_id in self._planning:

            # Run at the first call
            if self._planning[appointment_id].last_run is None:
                appointments.append(appointment_id)

            # Executions that always need to be scheduled
            elif self._planning[appointment_id].time_unit is TimeUnit.ALWAYS:
                appointments.append(appointment_id)

            else:

                # Get the current time
                now = datetime.now()

                # More seconds passed then the given interval
                if self._planning[appointment_id].time_unit is TimeUnit.SECOND:
                    last_run = self._planning[appointment_id].last_run
                    elapsed_time = now - last_run
                    seconds = elapsed_time.total_seconds()

                    if seconds >= self._planning[appointment_id].interval:
                        appointments.append(appointment_id)

                # More minutes passed then the given interval
                if self._planning[appointment_id].time_unit is TimeUnit.MINUTE:
                    last_run = self._planning[appointment_id].last_run
                    elapsed_time = now - last_run
                    minutes = divmod(elapsed_time.total_seconds(), 60)

                    if minutes[0] >= self._planning[appointment_id].interval:
                        appointments.append(appointment_id)

                # More hours run then the given interval
                elif self._planning[appointment_id].time_unit is TimeUnit.HOUR:
                    last_run = self._planning[appointment_id].last_run
                    elapsed_time = now - last_run
                    hours = divmod(elapsed_time.total_seconds(), 3600)

                    if hours[0] >= self._planning[appointment_id].interval:
                        appointments.append(appointment_id)

            for appointment in appointments:
                self._planning[appointment] = ExecutionTask(
                    self._planning[appointment].time_unit,
                    self._planning[appointment].interval,
                    datetime.now()
                )

        return appointments
