from investing_algorithm_framework import TradingStrategy, TimeUnit


class StrategyOne(TradingStrategy):
    strategy_id = "strategy_one"
    time_unit = TimeUnit.MINUTE
    interval = 1

    def run_strategy(self, context, data):
        pass
