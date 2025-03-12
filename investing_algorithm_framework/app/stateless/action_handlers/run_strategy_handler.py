import json

from investing_algorithm_framework.app.stateless.action_handlers \
    .action_handler_strategy import ActionHandlerStrategy


class RunStrategyHandler(ActionHandlerStrategy):
    MESSAGE = {"message": "Ok"}

    def handle_event(self, payload, algorithm):
        strategies = algorithm.strategy_orchestrator_service\
            .get_strategies(payload.get("strategies", None))
        tasks = algorithm.strategy_orchestrator_service.get_tasks()

        for strategy in strategies:
            context = algorithm.context
            algorithm.strategy_orchestrator_service.run_strategy(
                strategy=strategy,
                context=context,
                sync=True
            )

        for task in tasks:
            algorithm.strategy_orchestrator_service.run_task(
                task=task,
                algorithm=algorithm,
                sync=True
            )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": RunStrategyHandler.MESSAGE})
        }
