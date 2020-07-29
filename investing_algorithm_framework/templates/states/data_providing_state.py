from typing import List

from investing_algorithm_framework.core.context.algorithm_context \
    import AlgorithmContext
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.state import State
from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.core.executors import Executor
from investing_algorithm_framework.configuration.config_constants \
    import SETTINGS_MAX_CONCURRENT_WORKERS, DEFAULT_MAX_WORKERS
from investing_algorithm_framework.templates.data_providers.data_provider \
    import DataProviderInterface


class DataProvidingState(State):
    """
    Class DataProvidingState: State implementation for execution of instances
    of the DataProviderInterface.
    """

    registered_data_providers: List[Worker] = None

    from investing_algorithm_framework.templates.states.strategy_state \
        import StrategyState
    transition_state_class = StrategyState

    def __init__(self, algorithm_context: AlgorithmContext) -> None:
        super(DataProvidingState, self).__init__(algorithm_context)

        if self.registered_data_providers is None \
                or len(self.registered_data_providers) < 1:
            raise OperationalException(
                "Data providing state has not any data providers configured."
            )

    def run(self) -> None:

        # Execute all the data providers
        executor = Executor(
            workers=self.registered_data_providers,
            max_concurrent_workers=self.algorithm_context.config.get(
                SETTINGS_MAX_CONCURRENT_WORKERS, DEFAULT_MAX_WORKERS
            )
        )
        executor.start()

    @staticmethod
    def register_data_providers(data_providers: List) -> None:

        for data_provider in data_providers:

            assert isinstance(data_provider, Worker), (
                'Data provider {} must be of type '
                'Worker'.format(data_provider.__class__)
            )

            assert isinstance(data_provider, DataProviderInterface), (
                'Data provider {} must be of type '
                'DataProviderInterface'.format(data_provider.__class__)
            )

        DataProvidingState.registered_data_providers = data_providers
