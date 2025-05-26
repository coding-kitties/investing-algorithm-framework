import json

from investing_algorithm_framework.app.stateless.action_handlers \
    .action_handler_strategy import ActionHandlerStrategy


class RunStrategyHandler(ActionHandlerStrategy):
    """
    RunStrategyHandler is an action handler that runs a strategy and its tasks
    synchronously.

    If the run was successful, it returns a 200 OK response with a message
    "OK".
    """
    MESSAGE = {"message": "Ok"}

    def handle_event(self, payload, context, strategy_orchestrator_service):
        strategies = strategy_orchestrator_service\
            .get_strategies(payload.get("strategies", None))
        tasks = strategy_orchestrator_service.get_tasks()

        for strategy in strategies:
            strategy_orchestrator_service.run_strategy(
                strategy=strategy,
                context=context,
                sync=True
            )

        for task in tasks:
            strategy_orchestrator_service.run_task(
                task=task,
                context=context,
                sync=True
            )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": RunStrategyHandler.MESSAGE})
        }
