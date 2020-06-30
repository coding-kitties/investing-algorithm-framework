from typing import List

from investing_algorithm_framework.core.context.context import Context
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.state import State
from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.core.executors import Executor
from investing_algorithm_framework.configuration.config_constants \
    import DEFAULT_MAX_WORKERS, SETTINGS_MAX_WORKERS


class DataProvidingState(State):
    """
    Class DataProvidingState: State implementation for execution of instances
    of the DataProviderInterface.

    The state makes use of an Executor instance. After running this state,
    the state will transition to the OrderingState.
    """

    registered_data_providers: List[Worker] = None

    from investing_algorithm_framework.templates.states.strategy_state \
        import StrategyState
    transition_state_class = StrategyState

    # data_provider_scheduler: DataProviderScheduler = None

    def __init__(self, context: Context) -> None:
        super(DataProvidingState, self).__init__(context)

        if self.registered_data_providers is None \
                or len(self.registered_data_providers) < 1:
            raise OperationalException(
                "Data providing state has not any data providers configured."
            )

    def run(self) -> None:

        # Execute all the data providers
        executor = Executor(
            workers=self.registered_data_providers,
            max_concurrent_workers=self.context.settings.get(
                SETTINGS_MAX_WORKERS, DEFAULT_MAX_WORKERS
            )
        )
        executor.start()

    @staticmethod
    def register_data_providers(data_providers: List[Worker]) -> None:
        DataProvidingState.registered_data_providers = data_providers
