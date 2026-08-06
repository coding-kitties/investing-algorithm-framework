from investing_algorithm_framework import TradingStrategy, TimeUnit, Schedule


class StrategyOne(TradingStrategy):
    id = "strategy_one"
    schedule = Schedule.every(1, TimeUnit.MINUTE)
    def run_strategy(self, context, data):
        pass
