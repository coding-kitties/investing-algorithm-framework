from investing_algorithm_framework.app.stateless.action_handlers \
    import ActionHandler
from investing_algorithm_framework.app.stateless.action_handlers import Action
from investing_algorithm_framework.app.stateless.exception_handler import \
    handle_exception


class StatelessHandler:

    def handler(self, payload, context):
        try:
            # Handle the action
            action_handler = ActionHandler.of(
                Action.from_string(payload["action"]))
            return action_handler.handle(payload)
        except Exception as e:
            return handle_exception(e)
