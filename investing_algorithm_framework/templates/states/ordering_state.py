from typing import List

from investing_algorithm_framework.core.executors import Executor
from investing_algorithm_framework.core.state import State
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.configuration.config_constants import \
    SETTINGS_MAX_CONCURRENT_WORKERS, DEFAULT_MAX_WORKERS
from investing_algorithm_framework.templates.order_executors.order_executor \
    import OrderExecutorInterface


class OrderingState(State):

    from investing_algorithm_framework.templates.states.data_providing_state \
        import DataProvidingState
    transition_state_class = DataProvidingState

    registered_order_executors: List[Worker] = None

    def __init__(self, context) -> None:
        super(OrderingState, self).__init__(context)

        if self.registered_order_executors is None \
                or len(self.registered_order_executors) < 1:
            raise OperationalException(
                "OrderingState state has not any order executors configured"
            )

    def run(self) -> None:

        # Execute all the order executors
        executor = Executor(
            workers=self.registered_order_executors,
            max_concurrent_workers=self.context.config.get(
                SETTINGS_MAX_CONCURRENT_WORKERS, DEFAULT_MAX_WORKERS
            )
        )
        executor.start()

    @staticmethod
    def register_order_executors(order_executors: List) -> None:

        for order_executor in order_executors:
            assert isinstance(order_executor, Worker), (
                'Order executor {} must be of type '
                'Worker'.format(order_executor.__class__)
            )

            assert isinstance(order_executor, OrderExecutorInterface), (
                'Order executor {} must be of type '
                'OrderExecutorInterface'.format(order_executor.__class__)
            )

        OrderingState.registered_order_executors = order_executors
