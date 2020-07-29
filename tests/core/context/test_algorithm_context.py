import pytest
from investing_algorithm_framework.core.context import AlgorithmContext
from investing_algorithm_framework.core.state import State
from investing_algorithm_framework.core.exceptions import OperationalException


class TestStateOne(State):
    executed: bool = False

    def run(self) -> None:
        TestStateOne.executed = True


class TestStateTwo(State):
    executed: bool = False
    ending_state = True

    def run(self) -> None:
        TestStateTwo.executed = True


class TestStateThree:
    def run(self) -> None:
        pass


class WrongState:

    def running(self) -> None:
        pass


def test_register_initial_state() -> None:
    context = AlgorithmContext()
    context.register_initial_state(TestStateOne)

    assert isinstance(context._state, TestStateOne)

    context.register_initial_state(TestStateThree)

    assert isinstance(context._state, TestStateThree)

    with pytest.raises(OperationalException) as exc_info:
        context.register_initial_state(WrongState)

    assert str(exc_info.value) == "Provided state class has no run method"


def test_running() -> None:
    TestStateOne.transition_state_class = TestStateTwo

    context = AlgorithmContext()
    context.register_initial_state(TestStateOne)
    context.start()

    assert TestStateOne.executed
    assert TestStateTwo.executed
