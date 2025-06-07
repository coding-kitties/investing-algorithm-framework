from investing_algorithm_framework.domain.models import Event


class Observer:

    """
    Abstract base class for observers.
    Observers can be notified by observables about events.
    """

    def notify(self, event_type: Event, payload):
        """
        Update the observer with the event type and payload.

        Args:
            event_type: The type of event that occurred.
            payload: The data associated with the event.
        """
        raise NotImplementedError("Subclasses must implement this method.")
