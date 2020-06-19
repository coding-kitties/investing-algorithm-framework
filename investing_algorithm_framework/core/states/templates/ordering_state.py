from typing import List

from investing_algorithm_framework.core.states import BotState
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.order_executors import OrderExecutor


class OrderingState(BotState):

    from investing_algorithm_framework.core.states.templates.data_providing_state import DataProvidingState
    transition_state_class = DataProvidingState

    order_executors: List[OrderExecutor] = None

    def __init__(self, context) -> None:
        super(OrderingState, self).__init__(context)

        if self.order_executors is None or len(self.order_executors) < 1:
            raise OperationalException("OrderingState state has not any order executors configured")

    def run(self) -> None:

        for order_executor in OrderingState.order_executors:
            order_executor.execute_orders()

    @staticmethod
    def register_order_executors(order_executors: List[OrderExecutor]) -> None:
        OrderingState.order_executors = order_executors


