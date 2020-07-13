import pytest
from time import sleep
from investing_algorithm_framework.templates.states.strategy_state \
    import StrategyState
from investing_algorithm_framework.templates.strategies \
    import Strategy, ScheduledStrategy, RelationalStrategy
from investing_algorithm_framework.core.utils import TimeUnit
from investing_algorithm_framework.core.context import Context
from investing_algorithm_framework.core.events import Observer
from investing_algorithm_framework.core.workers import Worker


class TestObserver(Observer):
    updated: int = 0

    def update(self, observable, **kwargs) -> None:
        TestObserver.updated += 1


class CustomStrategyState(StrategyState):

    def get_transition_state_class(self):
        return None


class TestStrategy(Strategy):

    id = 'TestStrategyOne'

    def apply_strategy(self) -> None:
        pass


class TestScheduledStrategy(ScheduledStrategy):
    id = 'TestStrategyTwo'
    time_interval = 1
    time_unit = TimeUnit.SECOND

    def apply_strategy(self) -> None:
        pass


class TestRelationalStrategy(RelationalStrategy):
    id = 'TestStrategyThree'
    run_after = TestScheduledStrategy

    def apply_strategy(self) -> None:
        pass


class WrongStrategyOne:

    def provide_data(self) -> None:
        pass


class WrongStrategyTwo(Worker):

    def work(self, **kwargs) -> None:
        pass

    def provide_data(self) -> None:
        pass


def test() -> None:
    observer = TestObserver()
    strategy_one = TestStrategy()
    strategy_one.add_observer(observer)
    strategy_two = TestScheduledStrategy()
    strategy_two.add_observer(observer)
    strategy_three = TestRelationalStrategy()
    strategy_three.add_observer(observer)

    context = Context()
    CustomStrategyState.register_strategies([strategy_one, strategy_two])
    strategy_state = CustomStrategyState(context)
    strategy_state.start()

    assert len(strategy_state.registered_strategies) == 2
    assert observer.updated == 2

    sleep(1)

    CustomStrategyState.register_strategies(
        [strategy_one, strategy_two, strategy_three]
    )
    strategy_state = CustomStrategyState(context)
    strategy_state.start()

    assert len(strategy_state.registered_strategies) == 3
    assert observer.updated == 5

    with pytest.raises(Exception):
        strategy_state.register_strategies([
            WrongStrategyOne()
        ])

    with pytest.raises(Exception):
        strategy_state.register_strategies([
            WrongStrategyTwo()
        ])
