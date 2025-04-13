from abc import ABC, abstractmethod


class StateHandler(ABC):
    """
    Abstract base class for state handlers.

    This class defines the
    interface for state handlers, which are responsible for
    saving and loading state information.
    """

    @abstractmethod
    def initialize(self):
        """
        Initialize the state handler.
        """
        pass

    @abstractmethod
    def save(self, target_directory: str):
        """
        Save the state to the specified directory.

        Args:
            target_directory (str): Directory to save the state
        """
        pass

    @abstractmethod
    def load(self, target_directory: str):
        """
        Load the state from the specified directory.

        Args:
            target_directory (str): Directory to load the state
        """
        pass
