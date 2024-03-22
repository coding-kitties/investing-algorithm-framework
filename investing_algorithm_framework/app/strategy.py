from investing_algorithm_framework.domain import \
    TimeUnit, StrategyProfile, Trade
from .algorithm import Algorithm
from investing_algorithm_framework.domain import OperationalException


class TradingStrategy:
    time_unit: str = None
    interval: int = None
    worker_id: str = None
    strategy_id: str = None
    decorated = None
    market_data_sources = None

    def __init__(
        self,
        strategy_id=None,
        time_unit=None,
        interval=None,
        market_data_sources=None,
        worker_id=None,
        decorated=None
    ):

        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if interval is not None:
            self.interval = interval

        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if market_data_sources is not None:
            self.market_data_sources = market_data_sources

        if decorated is not None:
            self.decorated = decorated

        if worker_id is not None:
            self.worker_id = worker_id
        elif self.decorated:
            self.worker_id = decorated.__name__
        else:
            self.worker_id = self.__class__.__name__

        if strategy_id is not None:
            self.strategy_id = strategy_id

        # Check if time_unit is None
        if self.time_unit is None:
            raise OperationalException(
                f"Time unit not set for strategy instance {self.strategy_id}"
            )

        # Check if interval is None
        if self.interval is None:
            raise OperationalException(
                f"Interval not set for strategy instance {self.strategy_id}"
            )

    def run_strategy(self, algorithm, market_data):
        self.apply_strategy(algorithm=algorithm, market_data=market_data)

    def apply_strategy(self, algorithm, market_data):
        if self.decorated:
            self.decorated(algorithm=algorithm, market_data=market_data)
        else:
            raise NotImplementedError("Apply strategy is not implemented")

    @property
    def strategy_profile(self):
        return StrategyProfile(
            strategy_id=self.worker_id,
            interval=self.interval,
            time_unit=self.time_unit,
            market_data_sources=self.market_data_sources
        )

    def on_trade_closed(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_created(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_opened(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_stop_loss_triggered(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_triggered(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_triggered(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_stop_loss_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_updated(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_stop_loss_created(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_created(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_created(self, algorithm: Algorithm, trade: Trade):
        pass

    @property
    def strategy_identifier(self):

        if self.strategy_id is not None:
            return self.strategy_id

        return self.worker_id
