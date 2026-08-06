from investing_algorithm_framework.domain import \
    OperationalException, Schedule


class Task:
    schedule: Schedule = None
    worker_id: str = None
    decorated = None

    def __init__(
        self,
        schedule: Schedule = None,
        worker_id=None,
        decorated=None
    ):
        if schedule is not None:
            self.schedule = schedule
        else:
            class_schedule = getattr(self.__class__, 'schedule', None)
            if isinstance(class_schedule, Schedule):
                self.schedule = class_schedule
            else:
                raise OperationalException(
                    "Task requires a Schedule. Pass ``schedule=`` to the "
                    "constructor or set ``schedule = Schedule.every(...)`` "
                    "on the class. The legacy ``time_unit``/``interval`` "
                    "API was removed in v9.0."
                )

        if decorated is not None:
            self.decorated = decorated

        if worker_id is not None:
            self.worker_id = worker_id
        elif self.decorated:
            self.worker_id = decorated.__name__
        else:
            self.worker_id = self.__class__.__name__

    def run(self, context):

        if self.decorated:
            self.decorated(context=context)
        else:
            raise NotImplementedError(
                "run method must be implemented in the subclass"
            )
