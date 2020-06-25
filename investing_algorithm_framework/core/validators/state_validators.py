from abc import abstractmethod, ABC


class StateValidator(ABC):
    """
    Class StateValidator: validates the given state. Use this class to change
    the transition process of a state. Use it as a hook to decide if a
    state must transition, e.g. only change to a strategies state if all the
    provided data_providers meets a certain threshold.
    """

    @abstractmethod
    def validate_state(self, state) -> bool:
        pass
