from investing_algorithm_framework import TradingStrategy, TimeUnit


class StrategyTwo(TradingStrategy):
    strategy_id = "strategy_two"
    time_unit = TimeUnit.MINUTE
    interval = 1

    def run_strategy(self, context, market_data):
        pass
