from investing_algorithm_framework.app.stateless.action_handlers \
    import ActionHandler
from investing_algorithm_framework.app.stateless.action_handlers import \
    StatelessAction
from investing_algorithm_framework.app.stateless.exception_handler import \
    handle_exception
from investing_algorithm_framework.domain.exceptions import \
    OperationalException


class StatelessHandler:

    def handler(self, payload, algorithm):
        action = StatelessHandler.get_action_type(payload)

        try:
            # Handle the action
            action_handler = ActionHandler.of(StatelessAction
                                              .from_string(action))
            return action_handler.handle(payload)
        except Exception as e:
            return handle_exception(e)

    @staticmethod
    def get_action_type(payload):

        if "action" in payload:
            action = payload["action"]
        else:
            action = payload["ACTION"]

        if action is None:
            raise OperationalException("Action type not supported")

        return action
