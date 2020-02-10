from abc import abstractmethod, ABC

class StateValidator(ABC):

    @abstractmethod
    def validate_state(self, state) -> bool:
        pass
