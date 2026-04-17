
from typing import Dict, Any

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, PositionSize, StopLossRule, TakeProfitRule, \
    ScalingRule, TradingCost


class EMACrossoverRSIFFilterStrategy(TradingStrategy):

    def __init__(
        self,
        algorithm_id: str,
        symbols: list[str],
        trading_symbol: str,
        rsi_timeframe: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_timeframe,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window,
        ema_long_result_column="ema_long",
        ema_short_result_column="ema_short",
        ema_crossunder_result_column="ema_crossunder",
        ema_crossover_result_column="ema_crossover",
        rsi_result_column="rsi",
        time_unit: TimeUnit = TimeUnit.HOUR,
        interval: int = 2,
        market: str = "BITVAVO",
        metadata: dict = None,
        # Risk management parameters
        stop_loss_percentage: float = 5.0,
        take_profit_percentage: float = 10.0,
        trailing_stop_loss: bool = True,
        # Scaling parameters
        max_entries: int = 1,
        scale_in_percentage: float = 100,
        cooldown_in_bars: int = 0,
        # Trading cost parameters
        fee_percentage: float = 0.1,
        slippage_percentage: float = 0.05,
    ):
        self.rsi_timeframe = rsi_timeframe
        self.rsi_period = rsi_period
        self.rsi_result_column = rsi_result_column
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_timeframe = ema_timeframe
        self.ema_short_result_column = ema_short_result_column
        self.ema_long_result_column = ema_long_result_column
        self.ema_crossunder_result_column = ema_crossunder_result_column
        self.ema_crossover_result_column = ema_crossover_result_column
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window

        # Determine the warmup window needed (largest indicator period)
        warmup = max(ema_long_period, ema_short_period, rsi_period) + 10

        data_sources = []
        position_sizes = []
        stop_losses = []
        take_profits = []
        scaling_rules = []
        trading_costs = []

        for symbol in symbols:
            full_symbol = f"{symbol}/{trading_symbol}"
            data_sources.append(
                DataSource(
                    identifier=f"rsi_data_{symbol}",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_timeframe,
                    market=market,
                    symbol=full_symbol,
                    warmup_window=warmup,
                    pandas=True
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"ema_data_{symbol}",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_timeframe,
                    market=market,
                    symbol=full_symbol,
                    warmup_window=warmup,
                    pandas=True
                )
            )
            position_sizes.append(
                PositionSize(
                    symbol=symbol,
                    percentage_of_portfolio=1 / len(symbols)
                )
            )
            stop_losses.append(
                StopLossRule(
                    symbol=symbol,
                    percentage_threshold=stop_loss_percentage,
                    sell_percentage=100,
                    trailing=trailing_stop_loss,
                )
            )
            take_profits.append(
                TakeProfitRule(
                    symbol=symbol,
                    percentage_threshold=take_profit_percentage,
                    sell_percentage=100,
                )
            )
            scaling_rules.append(
                ScalingRule(
                    symbol=symbol,
                    max_entries=max_entries,
                    scale_in_percentage=scale_in_percentage,
                    cooldown_in_bars=cooldown_in_bars,
                )
            )
            trading_costs.append(
                TradingCost(
                    symbol=symbol,
                    fee_percentage=fee_percentage,
                    slippage_percentage=slippage_percentage,
                )
            )

        super().__init__(
            algorithm_id=algorithm_id,
            symbols=symbols,
            trading_symbol=trading_symbol,
            data_sources=data_sources,
            position_sizes=position_sizes,
            stop_losses=stop_losses,
            take_profits=take_profits,
            scaling_rules=scaling_rules,
            trading_costs=trading_costs,
            time_unit=time_unit,
            interval=interval,
            metadata=metadata,
        )

        # Store parameters so they get saved to parameters.json
        self.set_parameters({
            "ema_timeframe": ema_timeframe,
            "rsi_timeframe": rsi_timeframe,
            "ema_short_period": ema_short_period,
            "ema_long_period": ema_long_period,
            "ema_cross_lookback_window": ema_cross_lookback_window,
            "rsi_period": rsi_period,
            "rsi_overbought_threshold": rsi_overbought_threshold,
            "rsi_oversold_threshold": rsi_oversold_threshold,
            "stop_loss_percentage": stop_loss_percentage,
            "take_profit_percentage": take_profit_percentage,
            "trailing_stop_loss": trailing_stop_loss,
            "max_entries": max_entries,
            "scale_in_percentage": scale_in_percentage,
            "cooldown_in_bars": cooldown_in_bars,
            "fee_percentage": fee_percentage,
            "slippage_percentage": slippage_percentage,
        })

    def prepare_indicators(
        self,
        rsi_data,
        ema_data
    ):
        ema_data = ema(
            ema_data,
            period=self.ema_short_period,
            source_column="Close",
            result_column=self.ema_short_result_column
        )
        ema_data = ema(
            ema_data,
            period=self.ema_long_period,
            source_column="Close",
            result_column=self.ema_long_result_column
        )
        # Detect crossover (short EMA crosses above long EMA)
        ema_data = crossover(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column
        )
        # Detect crossunder (short EMA crosses below long EMA)
        ema_data = crossunder(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column
        )
        rsi_data = rsi(
            rsi_data,
            period=self.rsi_period,
            source_column="Close",
            result_column=self.rsi_result_column
        )

        return ema_data, rsi_data

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:

        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"ema_data_{symbol}"
            rsi_data_identifier = f"rsi_data_{symbol}"
            ema_data, rsi_data = self.prepare_indicators(
                ema_data=data[ema_data_identifier],
                rsi_data=data[rsi_data_identifier]
            )

            # use only RSI column
            rsi_oversold = rsi_data[self.rsi_result_column] \
                        < self.rsi_oversold_threshold

            crossover = ema_data[self.ema_crossover_result_column] \
                .rolling(window=self.ema_cross_lookback_window).sum() > 0
            buy_signal = rsi_oversold & crossover
            buy_signal = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signal

        return signals

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """
        Generate sell signals based on the moving average crossover.

        Args:
            data (pd.DataFrame): DataFrame containing OHLCV data.

        Returns:
            pd.Series: Series of sell signals (1 for sell, 0 for no action).
        """
        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"ema_data_{symbol}"
            rsi_data_identifier = f"rsi_data_{symbol}"

            ema_data, rsi_data = self.prepare_indicators(
                ema_data=data[ema_data_identifier],
                rsi_data=data[rsi_data_identifier]
            )

            # # use only RSI column
            rsi_overbought = rsi_data[self.rsi_result_column] \
                        >= self.rsi_overbought_threshold

            # Check that within the lookback window there was a crossunder
            crossunder = ema_data[self.ema_crossunder_result_column] \
                .rolling(window=self.ema_cross_lookback_window).sum() > 0

            sell_signal = crossunder & rsi_overbought
            sell_signal = sell_signal.fillna(False).astype(bool)
            signals[symbol] = sell_signal

        return signals
