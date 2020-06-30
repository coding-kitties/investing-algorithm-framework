from typing import List

from investing_algorithm_framework.core.state import State
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.executors import Executor
from investing_algorithm_framework.configuration.config_constants \
    import DEFAULT_MAX_WORKERS, SETTINGS_MAX_WORKERS
from investing_algorithm_framework.core.workers import Worker


class StrategyState(State):
    """
    Class StrategyState: State implementation for execution of instance of
    the StrategyInterface.

    The state makes use of an Executor instance. After running this state,
    the state will transition to the OrderingState.
    """

    registered_strategies: List[Worker] = None

    def __init__(self, context) -> None:
        super(StrategyState, self).__init__(context)

        if self.registered_strategies is None \
                or len(self.registered_strategies) < 1:
            raise OperationalException(
                "Strategy state has not any strategies configured."
            )

    def run(self) -> None:

        # Execute all the strategies
        executor = Executor(
            workers=self.registered_strategies,
            max_concurrent_workers=self.context.settings.get(
                SETTINGS_MAX_WORKERS, DEFAULT_MAX_WORKERS
            )
        )
        executor.start()

    @staticmethod
    def register_strategies(strategies: List) -> None:
        StrategyState.registered_strategies = strategies

    def get_transition_state_class(self):
        from investing_algorithm_framework.templates.states.ordering_state \
            import OrderingState
        return OrderingState
