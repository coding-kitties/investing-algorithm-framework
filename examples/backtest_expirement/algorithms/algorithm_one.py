from investing_algorithm_framework import TradingStrategy, Algorithm, TimeUnit

algorithm = Algorithm()


class Strategy(TradingStrategy):
    strategy_id = "strategy_one"
    time_unit = TimeUnit.MINUTE
    interval = 30

    def run_strategy(self, algorithm: Algorithm, market_data):
        pass


algorithm.add_strategy(Strategy())
