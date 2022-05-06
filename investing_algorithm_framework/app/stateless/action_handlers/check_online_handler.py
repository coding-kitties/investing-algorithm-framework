from investing_algorithm_framework.app.stateless.action_handlers \
    .action_handler_strategy import ActionHandlerStrategy


class CheckOnlineHandler(ActionHandlerStrategy):
    ONLINE_MESSAGE = {"ONLINE": "OK"}

    def handle_event(self, payload, algorithm_context):
        return CheckOnlineHandler.ONLINE_MESSAGE
