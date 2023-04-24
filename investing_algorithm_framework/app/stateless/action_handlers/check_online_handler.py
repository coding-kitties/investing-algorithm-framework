import json
from investing_algorithm_framework.app.stateless.action_handlers \
    .action_handler_strategy import ActionHandlerStrategy


class CheckOnlineHandler(ActionHandlerStrategy):
    MESSAGE = {"message": "online"}

    def handle_event(self, payload, algorithm):
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(CheckOnlineHandler.MESSAGE)
        }
