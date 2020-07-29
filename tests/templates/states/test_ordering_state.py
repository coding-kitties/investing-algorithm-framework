import pytest
from time import sleep
from investing_algorithm_framework.templates.states.ordering_state \
    import OrderingState
from investing_algorithm_framework.templates.order_executors \
    import OrderExecutor, ScheduledOrderExecutor, RelationalOrderExecutor
from investing_algorithm_framework.core.utils import TimeUnit
from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.workers import Worker


class TestObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        TestObserver.updated += 1


class CustomOrderingState(OrderingState):

    def get_transition_state_class(self):
        return None


class TestOrderExecutor(OrderExecutor):

    id = 'TestOrderExecutorOne'

    def execute_orders(self) -> None:
        pass


class TestScheduledOrderExecutor(ScheduledOrderExecutor):

    id = 'TestOrderExecutorTwo'
    time_interval = 1
    time_unit = TimeUnit.SECOND

    def execute_orders(self) -> None:
        pass


class TestRelationalOrderExecutor(RelationalOrderExecutor):
    id = 'TestOrderExecutorThree'
    run_after = TestScheduledOrderExecutor

    def execute_orders(self) -> None:
        pass


class WrongOrderExecutorOne:

    def execute_orders(self) -> None:
        pass


class WrongOrderExecutorTwo(Worker):

    def work(self, **kwargs) -> None:
        pass

    def execute_orders(self) -> None:
        pass


def test() -> None:
    observer = TestObserver()
    order_executor_one = TestOrderExecutor()
    order_executor_one.add_observer(observer)
    order_executor_two = TestScheduledOrderExecutor()
    order_executor_two.add_observer(observer)
    order_executor_three = TestRelationalOrderExecutor()
    order_executor_three.add_observer(observer)

    context = AlgorithmContext()
    CustomOrderingState.register_order_executors(
        [order_executor_one, order_executor_two]
    )
    ordering_state = CustomOrderingState(context)
    ordering_state.start()

    assert len(ordering_state.registered_order_executors) == 2
    assert observer.updated == 2

    sleep(1)

    CustomOrderingState.register_order_executors(
        [order_executor_one, order_executor_two, order_executor_three]
    )
    ordering_state = CustomOrderingState(context)
    ordering_state.start()

    assert len(ordering_state.registered_order_executors) == 3
    assert observer.updated == 5

    with pytest.raises(Exception):
        ordering_state.register_order_executors([
            WrongOrderExecutorOne()
        ])

    with pytest.raises(Exception):
        ordering_state.register_order_executors([
            WrongOrderExecutorTwo()
        ])
