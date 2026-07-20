from typing import Any, Dict, Iterable

from pyindicators import crossover, crossunder, ema

from investing_algorithm_framework import (
    DataSource,
    PositionSize,
    Schedule,
    Signal,
    SignalSeries,
    SignalSide,
    TimeUnit,
    TradingStrategy,
    signal_series_from_column,
    signals_from_column,
)


class CrossOverStrategyV1(TradingStrategy):
    """
    A simple trading strategy that uses EMA crossovers to generate buy and
    sell signals. The strategy uses a 50-period EMA and a 100-period EMA
    to detect golden and death crosses. It also uses a 200-period EMA to
    determine the overall trend direction. The strategy trades BTC/EUR
    on a 2-hour timeframe. The strategy is designed to be used with the
    Investing Algorithm Framework and uses the PyIndicators library
    to calculate the EMAs and crossover signals.

    The strategy uses a trailing stop loss and take profit to manage
    risk. The stop loss is set to 5% below the entry price and the
    take profit is set to 10% above the entry price. The stop loss and
    take profit are both trailing, meaning that they will move up
    with the price when the price goes up.
    """
    schedule = Schedule.every(2, TimeUnit.HOUR)
    fast = 50
    slow = 100
    trend = 200
    stop_loss_percentage = 2
    stop_loss_sell_size = 50
    take_profit_percentage = 8
    take_profit_sell_size = 50
    position_sizes = [
        PositionSize(
            symbol="BTC", percentage_of_portfolio=20.0
        )
    ]

    def __init__(
        self,
        algorithm_id: str = "crossover_strategy_v1",
        symbols=["BTC"],
        ema_time_frame="2h",
        ema_crossover_result_column="ema_crossover",
        ema_crossunder_result_column="ema_crossunder",
        crossover_lookback_window=4,
    ):
        self.ema_time_frame = ema_time_frame
        self.ema_cross_lookback_window = crossover_lookback_window
        self.ema_crossover_result_column = ema_crossover_result_column
        self.ema_crossunder_result_column = ema_crossunder_result_column
        super().__init__(algorithm_id=algorithm_id, symbols=symbols)

        for symbol in symbols:
            full_symbol = f"{symbol}/EUR"
            self.data_sources.append(
                DataSource(
                    market="BITVAVO",
                    symbol=full_symbol,
                    data_type="ohlcv",
                    time_frame=self.ema_time_frame,
                    warmup_window=self.trend,
                    identifier=f"{full_symbol}-ohlcv-2h",
                    pandas=True
                )
            )

    def _prepare_indicators(self, ema_data):
        ema_data = ema(
            ema_data,
            period=self.fast,
            source_column="Close",
            result_column=f"ema_{self.fast}"
        )
        ema_data = ema(
            ema_data,
            period=self.slow,
            source_column="Close",
            result_column=f"ema_{self.slow}"
        )
        ema_data = crossunder(
            ema_data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.slow}",
            result_column=self.ema_crossunder_result_column
        )
        ema_data = crossover(
            ema_data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.slow}",
            result_column=self.ema_crossover_result_column
        )
        # Rolling-max within lookback window so a fresh crossover stays
        # active for ``ema_cross_lookback_window`` bars.
        ema_data["entry"] = (
            ema_data[self.ema_crossover_result_column]
            .rolling(window=self.ema_cross_lookback_window)
            .max().fillna(False).astype(bool)
        )
        ema_data["exit"] = (
            ema_data[self.ema_crossunder_result_column]
            .rolling(window=self.ema_cross_lookback_window)
            .max().fillna(False).astype(bool)
        )
        return ema_data

    # ---- v9 event-mode API ---------------------------------------- #
    def generate_signals(
        self, context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        for symbol in self.symbols:
            symbol_pair = f"{symbol}/EUR"
            frame = self._prepare_indicators(data[f"{symbol_pair}-ohlcv-2h"])
            yield from signals_from_column(
                frame, "entry",
                side=SignalSide.OPEN_LONG,
                symbol=symbol,
                source="ema_cross",
            )
            yield from signals_from_column(
                frame, "exit",
                side=SignalSide.CLOSE_LONG,
                symbol=symbol,
                source="ema_cross",
            )

    # ---- v9 vector-mode API --------------------------------------- #
    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        for symbol in self.symbols:
            symbol_pair = f"{symbol}/EUR"
            frame = self._prepare_indicators(
                data[f"{symbol_pair}-ohlcv-2h"].copy()
            )
            yield signal_series_from_column(
                frame, "entry",
                side=SignalSide.OPEN_LONG,
                symbol=symbol,
                source="ema_cross",
            )
            yield signal_series_from_column(
                frame, "exit",
                side=SignalSide.CLOSE_LONG,
                symbol=symbol,
                source="ema_cross",
            )
