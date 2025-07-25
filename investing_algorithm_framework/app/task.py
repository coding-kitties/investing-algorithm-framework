from investing_algorithm_framework.domain import \
    TimeUnit


class Task:
    time_unit: str = None
    interval: int = None
    worker_id: str = None
    decorated = None

    def __init__(
        self,
        time_unit=None,
        interval=None,
        worker_id=None,
        decorated=None
    ):
        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if interval is not None:
            self.interval = interval

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
