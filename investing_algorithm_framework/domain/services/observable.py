from investing_algorithm_framework.domain.models import Event


class Observable:
    """
    Abstract base class for observable objects.
    Observables can be observed by observers that
    implement the Observer interface.
    """

    def __init__(self):
        super().__init__()  # Important in diamond inheritance
        self._observers = []

    def add_observer(self, observer):
        """
        Add an observer to the observable.

        Args:
            observer: An object that implements the Observer interface.
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer):
        """
        Remove an observer from the observable.

        Args:
            observer: An object that implements the Observer interface.
        """
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, event_type: Event, payload):
        """
        Notify all observers about an event.

        Args:
            event_type (Event): The type of event to notify observers about.
            payload: The data to pass to the observers.
        """
        for observer in self._observers:
            observer.notify(event_type, payload)

    def clear_observers(self):
        """
        Clear all observers from the observable.
        This is useful for resetting the state of the observable.
        """
        self._observers.clear()
