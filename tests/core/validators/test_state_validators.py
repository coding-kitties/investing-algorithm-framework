from investing_algorithm_framework.core.validators import StateValidator
from investing_algorithm_framework.core.state import State


class PreStateValidator(StateValidator):
    updated: int = 0

    def validate_state(self, state) -> bool:
        PreStateValidator.updated += 1
        return True


class PostStateValidator(StateValidator):
    updated: int = 0

    def validate_state(self, state) -> bool:
        print(state.cycles)
        PostStateValidator.updated += 1

        if state.cycles == 2:
            return True

        return False


class TestState(State):
    pre_state_validators = [PreStateValidator]
    post_state_validators = [PostStateValidator]
    transition_state_class = None
    cycles: int = 0

    def run(self) -> None:
        TestState.cycles += 1


def test() -> None:
    state = TestState()
    state.start()

    assert PreStateValidator.updated == 1
    assert PostStateValidator.updated == 2
    assert TestState.cycles == 2
