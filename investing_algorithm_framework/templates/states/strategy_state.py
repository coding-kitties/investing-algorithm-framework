import logging
import time
from typing import List

from investing_algorithm_framework.core.state import State
from investing_algorithm_framework.core.executors import ExecutionScheduler
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.core.executors import Executor
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.configuration.config_constants \
    import DEFAULT_MAX_WORKERS, SETTINGS_MAX_WORKERS

logger = logging.getLogger(__name__)


class StrategyExecutor(Executor):
    """
    Class StrategyExecutor: is an executor for Strategy instances.
    """

    def __init__(
            self,
            strategies: List = None,
            max_workers: int = DEFAULT_MAX_WORKERS
    ):
        super(StrategyExecutor, self).__init__(max_workers=max_workers)

        self._registered_strategies: List = []

        if strategies is not None and len(strategies) > 0:
            self._registered_strategies = strategies

    def create_workers(self) -> List[Worker]:
        return self._registered_strategies

    @property
    def registered_strategies(self) -> List:
        return self._registered_strategies

    @property
    def configured(self):
        return self._registered_strategies is not None \
               and len(self._registered_strategies) > 0


class StrategyScheduler(ExecutionScheduler):
    """
    Strategy scheduler that will function as a scheduler.
    """

    def __init__(self):
        self._configured = False
        super(StrategyScheduler, self).__init__()

    def configure(self, strategies: List) -> None:
        self._planning = {}

        for strategy in strategies:
            self.add_execution_task(
                execution_id=strategy.get_id(),
                time_unit=strategy.get_time_unit(),
                interval=strategy.get_time_interval()
            )

        self._configured = True

    @property
    def configured(self) -> bool:
        return self._configured


class StrategyState(State, Observer):

    registered_strategies: List = None
    strategy_scheduler: StrategyScheduler = None

    def __init__(self, context):
        super(StrategyState, self).__init__(context)
        self._updated = False
        self.strategy_executor = None

    def _schedule_strategies(self) -> List:

        if not StrategyState.strategy_scheduler:
            StrategyState.strategy_scheduler = StrategyScheduler()

        if not StrategyState.strategy_scheduler.configured:
            StrategyState.strategy_scheduler.configure(
                self.registered_strategies
            )

        planning = StrategyState.strategy_scheduler.schedule_executions()
        planned_strategies = []

        for strategy in self.registered_strategies:

            if strategy.get_id() in planning:
                planned_strategies.append(strategy)

        return planned_strategies

    def _start_strategies(self, strategies: List) -> None:

        self.strategy_executor = StrategyExecutor(
            strategies=strategies,
            max_workers=self.context.settings.get(
                SETTINGS_MAX_WORKERS, DEFAULT_MAX_WORKERS
            )
        )

        if self.strategy_executor.configured:
            self.strategy_executor.add_observer(self)
            self.strategy_executor.start()
        else:
            # Skip the execution
            self._updated = True

    def run(self) -> None:

        if self.registered_strategies is None:
            raise OperationalException(
                "Data providing state has not any data providers configured"
            )

        # Schedule the strategies providers
        planned_strategies = self._schedule_strategies()

        # Execute all the strategies providers
        self._start_strategies(planned_strategies)

        # Sleep till updated
        while not self._updated:
            time.sleep(1)

        # Collect all strategies from the strategies providers
        for strategies in self.strategy_executor.registered_strategies:
            logger.info("Strategy: {} finished running".format(
                strategies.get_id())
            )

    def update(self, observable, **kwargs) -> None:
        self._updated = True

    @staticmethod
    def register_strategies(strategies: List) -> None:
        StrategyState.registered_strategies = strategies

    def get_transition_state_class(self):
        from investing_algorithm_framework.templates.states.ordering_state \
            import OrderingState
        return OrderingState
