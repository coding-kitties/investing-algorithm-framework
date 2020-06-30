from abc import ABC
from typing import Dict, Any

from investing_algorithm_framework.core.workers.worker import Worker
from investing_algorithm_framework.core.exceptions import OperationalException


class RelationalWorker(Worker, ABC):
    """
    RelationalWorker will start after it's relational worker has run.

    It will check if the related worked had run, and if this is
    true it will start itself. Use this worker if you want to create
    chains of workers that are depended on each other.
    """
    run_after: Worker

    def start(self, **kwargs: Dict[str, Any]) -> None:

        # Only run if the last time this worker stared is before
        # the last time the 'run_after' worker had finished.
        if not self.run_after:
            raise OperationalException(
                'The run_after worker is not set, make sure you set this '
                'attribute to let the RelationalWorker run properly.'
            )

        if self.last_run is not None:

            if self.run_after.last_run is None:
                raise OperationalException(
                    "Relational Worker has run before 'run_after' worker."
                )

            if self.run_after.last_run > self.last_run:
                super(RelationalWorker, self).start()

        elif self.run_after.last_run is not None:
            super(RelationalWorker, self).start()
