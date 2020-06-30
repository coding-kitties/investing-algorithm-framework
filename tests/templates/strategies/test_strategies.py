from investing_algorithm_framework.templates.strategies import Strategy, \
    ScheduledStrategy, RelationalStrategy
from investing_algorithm_framework.core.utils import TimeUnit
from investing_algorithm_framework.core.events import Observer


class TestObserver(Observer):
    update_count: int = 0

    def update(self, observable, **kwargs) -> None:
        self.update_count += 1


class TestStrategy(Strategy):
    id = 'TestStrategy'

    def apply_strategy(self) -> None:
        pass


class TestScheduledStrategy(ScheduledStrategy):
    id = 'TestScheduledStrategy'
    time_unit = TimeUnit.SECOND
    time_interval = 1

    def apply_strategy(self) -> None:
        pass


class TestRelationalStrategy(RelationalStrategy):
    id = 'TestRelationalStrategy'
    run_after = TestScheduledStrategy

    def apply_strategy(self) -> None:
        pass


def test():
    strategy_one = TestStrategy()

    assert strategy_one.id is not None
    assert strategy_one.get_id() == TestStrategy.id

    observer = TestObserver()
    strategy_one.add_observer(observer)

    # Run the strategy
    strategy_one.start()

    # Observer must have been updated
    assert observer.update_count == 1

    strategy_two = TestScheduledStrategy()

    assert strategy_two.id is not None
    assert strategy_two.get_id() == TestScheduledStrategy.id

    strategy_two.add_observer(observer)

    # Run the strategy
    strategy_two.start()

    # Observer must have been updated
    assert observer.update_count == 2

    strategy_three = TestRelationalStrategy()

    assert strategy_three.id is not None
    assert strategy_three.get_id() == TestRelationalStrategy.id

    strategy_three.add_observer(observer)

    # Run the strategy
    strategy_three.start()

    # Observer must have been updated
    assert observer.update_count == 3
