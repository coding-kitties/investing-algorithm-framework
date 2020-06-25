import logging

from investing_algorithm_framework.core.exceptions import ImproperlyConfigured
from investing_algorithm_framework.core.state import State

logger = logging.getLogger(__name__)


class SetupState(State):

    from investing_algorithm_framework.templates.states.data_providing_state \
        import DataProvidingState
    transition_state_class = DataProvidingState

    def __init__(self, context):
        super(SetupState, self).__init__(context)

    def run(self) -> None:
        """
        Running the setup state.
        """

        # Load the settings
        if not self.context.settings.configured:
            raise ImproperlyConfigured(
                "Settings module is not specified, make sure you have setup "
                "a investing_algorithm_framework project and the "
                "investing_algorithm_framework is valid or that you have "
                "specified the settings module in your manage.py-template file"
            )
