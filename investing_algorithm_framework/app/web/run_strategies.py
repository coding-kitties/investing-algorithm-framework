def run_strategies(strategy_orchestration_service):

    if strategy_orchestration_service.running:
        strategy_orchestration_service.run_pending_jobs()
