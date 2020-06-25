from investing_algorithm_framework.core.context import Context
from investing_algorithm_framework.core.state import State


class TestState(State):

    def run(self) -> None:
        pass


def test_singleton_instance() -> None:
    context_one = Context()
    context_two = Context()
    assert context_one is context_two


def test_initial_state() -> None:
    context = Context()
    context.register_initial_state(TestState)
    assert type(context._state) is TestState



