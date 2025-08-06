from typing import Dict, Any, List

from datetime import timedelta
import pandas as pd

from pyindicators import ema, crossover, crossunder, rsi

from investing_algorithm_framework import TradingStrategy, DataSource, Context, TimeFrame, TradeRiskType


class EMACrossoverRSIStrategy(TradingStrategy):
    """
    This is an example strategy that use the EMA Crossover and RSI indicators
    to generate buy and sell signals. It uses the EMA Crossover to determine
    the trend direction and the RSI to identify overbought and oversold conditions.

    This strategy implements both vectorized and non-vectorized methods for
    generating buy and sell signals. This strategy can therefore be used in
    both the vectorized and event-basesd backtest engines of the framework.

    Args:
        time_unit (str): The time unit for the strategy (e.g., "HOUR", "MINUTE").
        interval (int): The interval for the strategy.
        market (str): The market to trade on (e.g., "binance").
        symbols (List[str]): List of symbols to trade.
        data_sources (List[DataSource]): List of DataSource instances.
        ema_time_frame (str): Time frame for the EMA indicator.
        ema_short_period (int): Short period for the EMA indicator.
        ema_long_period (int): Long period for the EMA indicator.
        rsi_time_frame (str): Time frame for the RSI indicator.
        rsi_period (int): Period for the RSI indicator.
        rsi_oversold_threshold (float): Oversold threshold for RSI.
        rsi_overbought_threshold (float): Overbought threshold for RSI.
        alignment_window_size (int): Size of the alignment window in minutes
    """

    def __init__(
        self,
        time_unit,
        interval,
        market,
        symbols: List[str],
        data_sources,
        ema_time_frame,
        ema_short_period,
        ema_long_period,
        rsi_time_frame,
        rsi_period,
        rsi_oversold_threshold,
        rsi_overbought_threshold,
        alignment_window_size,
        trailing_stop_loss_percentage=5,
        trailing_take_profit_percentage=10,
        position_sizes: Dict[str, float] = None
    ):
        super().__init__(time_unit=time_unit, interval=interval)
        self.data_sources = data_sources
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_time_frame = ema_time_frame
        self.rsi_time_frame = rsi_time_frame
        self.rsi_period = rsi_period
        self.symbols = symbols
        self.alignment_window_size = alignment_window_size
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.market = market
        self.trailing_stop_loss_percentage = trailing_stop_loss_percentage
        self.trailing_take_profit_percentage = trailing_take_profit_percentage
        self.position_sizes = position_sizes

        if self.position_sizes is None:
            self.position_sizes = {symbol: ((100 / len(self.symbols)) - 2) for symbol in self.symbols}

    def get_position_size(self, symbol: str) -> float:
        """
        Get the position size for a given symbol.
        If the symbol is not in the position sizes, return 0.
        """
        return self.position_sizes.get(symbol, 0)

    def run_strategy(self, context: Context, data: Dict[str, Any]):

        for symbol in self.symbols:
            target_symbol = symbol.split("/")[0]
            # Skip if the symbol if there are open orders
            if context.has_open_orders(target_symbol):
                continue

            ema_data_identifier = f"OHLCV_{self.market}_{symbol}_{self.ema_time_frame}"
            rsi_data_identifier = f"OHLCV_{self.market}_{symbol}_{self.rsi_time_frame}"
            ema_data = data[ema_data_identifier].copy()
            rsi_data = data[rsi_data_identifier].copy()

            if rsi_data.empty or ema_data.empty:
                continue

            ema_data = ema(
                ema_data,
                source_column="Close",
                period=self.ema_short_period,
                result_column=f"ema_short"
            )
            ema_data = ema(
                ema_data,
                source_column="Close",
                period=self.ema_long_period,
                result_column=f"ema_long"
            )
            ema_data = crossunder(
                ema_data,
                first_column=f"ema_short",
                second_column=f"ema_long",
                result_column="ema_crossunder"
            )
            ema_data = crossover(
                ema_data,
                first_column=f"ema_short",
                second_column=f"ema_long",
                result_column="ema_crossover"
            )
            rsi_data = rsi(
                rsi_data,
                source_column="Close",
                period=self.rsi_period,
                result_column="rsi"
            )

            if context.has_position(target_symbol):

                if self.is_sell_signal(rsi_data, ema_data):
                    context.close_position(target_symbol)
            else:

                if self.is_buy_signal(rsi_data, ema_data):
                    price = rsi_data["Close"].iloc[-1]
                    order = context.create_limit_buy_order(
                        target_symbol=target_symbol,
                        price=price,
                        percentage_of_portfolio=self.get_position_size(symbol),
                    )
                    trade = context.get_trade(order_id=order.id)
                    context.add_stop_loss(
                        trade,
                        percentage=self.trailing_stop_loss_percentage,
                        trade_risk_type=TradeRiskType.TRAILING,
                        sell_percentage=50
                    )
                    context.add_take_profit(
                        trade,
                        percentage=self.trailing_take_profit_percentage,
                        trade_risk_type=TradeRiskType.TRAILING,
                        sell_percentage=50
                    )

    def buy_signal_vectorized(self, data: Dict[str, Any]) -> pd.Series:
        first_symbol = self.symbols[0]
        ema_data_identifier = "ema_data"
        rsi_data_identifier = "rsi_data"

        # Ensure data is sorted by index
        ema_data = data[ema_data_identifier].copy().sort_index()
        rsi_data = data[rsi_data_identifier].copy().sort_index()

        # --- 1. Calculate the EMA crossover signal on daily data ---
        ema_data = ema(
            ema_data,
            source_column="Close",
            period=self.ema_short_period,
            result_column=f"ema_short"
        )
        ema_data = ema(
            ema_data,
            source_column="Close",
            period=self.ema_long_period,
            result_column=f"ema_long"
        )
        ema_data = crossover(
            ema_data,
            first_column=f"ema_short",
            second_column=f"ema_long",
            result_column="ema_crossover"
        )

        # --- 2. Calculate the RSI oversold signal on 4-hour data ---
        rsi_data = rsi(
            rsi_data,
            source_column="Close",
            period=self.rsi_period,
            result_column="rsi"
        )
        oversold = rsi_data["rsi"] < self.rsi_oversold_threshold

        # --- 3. Align the EMA crossover signal to the 4-hour time frame ---
        # We use reindex with 'ffill' (forward-fill) to carry the daily signal
        # forward to all subsequent 4-hour data points until the next daily signal.
        # We also fill any initial NaNs with 0 (or False)
        ema_crossover_signal = ema_data["ema_crossover"].reindex(
            rsi_data.index,
            method="ffill"
        ).fillna(0)

        # --- 4. Now, both signals are on the same 4-hour index and can be combined ---
        # A rolling window is applied to the resampled EMA crossover signal
        # This ensures that the rolling window is also on the 4-hour timeframe
        cross = (ema_crossover_signal.rolling(self.alignment_window_size).max() == 1).shift(1)

        # --- 5. Combine the signals ---
        buy_signal = (cross & oversold)

        # --- 6. Post-process the signal ---
        # Convert to boolean and fill any remaining NaNs
        buy_signal = buy_signal.astype(bool).fillna(False)

        return buy_signal


    def sell_signal_vectorized(self, data: Dict[str, Any]) -> pd.Series:
        first_symbol = self.symbols[0]
        ema_data_identifier = "ema_data"
        rsi_data_identifier = "rsi_data"

        # Ensure data is sorted by index for reliable operations
        ema_data = data[ema_data_identifier].copy().sort_index()
        rsi_data = data[rsi_data_identifier].copy().sort_index()

        # --- 1. Calculate the EMA crossunder signal on daily data ---
        # (Assuming 'ema' and 'crossunder' functions are available in your environment)
        ema_data = ema(
            ema_data,
            source_column="Close",
            period=self.ema_short_period,
            result_column="ema_short"
        )
        ema_data = ema(
            ema_data,
            source_column="Close",
            period=self.ema_long_period,
            result_column="ema_long"
        )
        ema_data = crossunder(
            ema_data,
            first_column="ema_short",
            second_column="ema_long",
            result_column="ema_crossunder"
        )

        # --- 2. Calculate the RSI overbought signal on 4-hour data ---
        # (Assuming 'rsi' function is available in your environment)
        rsi_data = rsi(
            rsi_data,
            source_column="Close",
            period=self.rsi_period,
            result_column="rsi"
        )
        # Assuming a sell signal is triggered when RSI is overbought
        overbought = rsi_data["rsi"] > self.rsi_overbought_threshold

        # --- 3. Align the EMA crossunder signal to the 4-hour time frame ---
        # Resample the daily crossunder signal to the 4-hour index.
        # Use ffill to carry the daily signal forward until the next daily signal.
        # Fill any initial NaNs with 0 (or False)
        ema_crossunder_resampled = ema_data["ema_crossunder"].reindex(
            rsi_data.index,
            method="ffill"
        ).fillna(0)

        # --- 4. Determine when the crossunder signal is 'active' ---
        # Assuming crossunder function returns -1 for a crossunder
        crossunder_active = (ema_crossunder_resampled == 1).astype(bool)

        # --- 5. Combine the signals: Crossunder active AND RSI is overbought ---
        sell_signal = crossunder_active & overbought

        # --- 6. Filter for the first signal after the crossunder becomes active ---
        # This prevents multiple sell signals for the same crossunder event
        sell_signal_filtered = sell_signal.where(sell_signal).ffill()
        sell_signal = (sell_signal_filtered != sell_signal_filtered.shift(1)) & sell_signal

        # --- 7. Post-process the final signal ---
        # Convert to boolean and fill any remaining NaNs with False
        sell_signal = sell_signal.astype(bool).fillna(False)

        return sell_signal

    def is_sell_signal(self, rsi_data, ema_data) -> bool:
        """
        A buy or sell signal to occur if any RSI value in the selected (time-aligned) window is below (or above) the threshold — not just the last one.
        """
        rsi_tf = TimeFrame.from_value(self.rsi_time_frame)
        ema_tf = TimeFrame.from_value(self.ema_time_frame)

        # Determine the more granular (smaller) timeframe.
        # Example: If RSI is on 2h and EMA on 4h, then 2h is more granular.
        min_tf_minutes = min(rsi_tf.amount_of_minutes, ema_tf.amount_of_minutes)
        alignment_window_duration = timedelta(minutes=self.alignment_window_size * min_tf_minutes)

        # Define cutoff time based on latest timestamp in either series
        latest_time = max(rsi_data.index[-1], ema_data.index[-1])
        cutoff_time = latest_time - alignment_window_duration

        # Slice windows based on timestamps
        recent_ema = ema_data[ema_data.index >= cutoff_time]
        recent_rsi = rsi_data[rsi_data.index >= cutoff_time]

        if recent_ema.empty or recent_rsi.empty:
            return False

        # Check for crossunder condition and RSI overbought condition
        cross_condition = recent_ema["ema_crossunder"].max() == 1
        overbought_condition = recent_rsi["rsi"].gt(
            self.rsi_overbought_threshold
        ).any()
        return cross_condition and overbought_condition

    def is_buy_signal(self, rsi_data, ema_data) -> bool:
        """
        A buy or sell signal to occur if any RSI value in the selected (time-aligned) window is below (or above) the threshold — not just the last one.
        """
        rsi_tf = TimeFrame.from_value(self.rsi_time_frame)
        ema_tf = TimeFrame.from_value(self.ema_time_frame)

        # Determine the more granular (smaller) timeframe.
        # Example: If RSI is on 2h and EMA on 4h, then 2h is more granular.
        min_tf_minutes = min(
            rsi_tf.amount_of_minutes, ema_tf.amount_of_minutes
        )
        alignment_window_duration = timedelta(minutes=self.alignment_window_size * min_tf_minutes)

        # Define cutoff time based on latest timestamp in either series
        latest_time = max(
            rsi_data.index[-1], ema_data.index[-1]
        )
        cutoff_time = latest_time - alignment_window_duration

        # Slice windows based on timestamps
        recent_ema = ema_data[ema_data.index >= cutoff_time]
        recent_rsi = rsi_data[rsi_data.index >= cutoff_time]

        if recent_ema.empty or recent_rsi.empty:
            return False

        # Check for crossunder condition and RSI overbought condition
        cross_condition = recent_ema["ema_crossover"].max() == 1
        oversold_condition = recent_rsi["rsi"].lt(self.rsi_oversold_threshold).any()
        return cross_condition and oversold_condition
