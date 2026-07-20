from investing_algorithm_framework import TradingStrategy, TimeUnit, Schedule


class StrategyTwo(TradingStrategy):
    strategy_id = "strategy_two"
    schedule = Schedule.every(1, TimeUnit.MINUTE)
    def run_strategy(self, context, market_data):
        pass
