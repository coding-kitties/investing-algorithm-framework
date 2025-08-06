from typing import Dict, Any, List

from datetime import timedelta
import polars as pl

from pyindicators import ema, crossover, crossunder, rsi

from investing_algorithm_framework import TradingStrategy, Context, TradeRiskType


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
        ema_short_period,
        ema_long_period,
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

            data_id = f"OHLCV_{symbol}"
            data = data.get(data_id, None)

            # Check if the polars DataFrame is empty
            if data.is_empty():
                continue

            data = ema(
                data,
                source_column="Close",
                period=self.ema_short_period,
                result_column=f"ema_short"
            )
            data = ema(
                data,
                source_column="Close",
                period=self.ema_long_period,
                result_column=f"ema_long"
            )
            data = crossunder(
                data,
                first_column=f"ema_short",
                second_column=f"ema_long",
                result_column="ema_crossunder"
            )
            data = crossover(
                data,
                first_column=f"ema_short",
                second_column=f"ema_long",
                result_column="ema_crossover"
            )
            data = rsi(
                data,
                source_column="Close",
                period=self.rsi_period,
                result_column="rsi"
            )

            if context.has_position(target_symbol):

                if self.is_sell_signal(data):
                    context.close_position(
                        symbol=target_symbol,
                    )
            else:

                if self.is_buy_signal(data):
                    # Get the last price of the polar DataFrame
                    price = data["Close"][-1]
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

    def is_sell_signal(self, data: pl.DataFrame) -> bool:
        """
        A sell signal occurs if a 'ema_crossunder' just occurred in the latest row,
        and the max RSI in the alignment window is above the overbought threshold.
        """
        if data.is_empty() or "ema_crossunder" not in data.columns:
            return False

        last_row = data.slice(-1, 1).to_dicts()[0]
        if last_row["ema_crossunder"] != 1:
            return False

        window = data.slice(-self.alignment_window_size, self.alignment_window_size)
        rsi_above_threshold = window["rsi"].max() > self.rsi_overbought_threshold

        return rsi_above_threshold


    def is_buy_signal(self, data: pl.DataFrame) -> bool:
        """
        A buy signal occurs if an 'ema_crossover' just occurred in the latest row,
        and the min RSI in the alignment window is below the oversold threshold.
        """
        if data.is_empty() or "ema_crossover" not in data.columns:
            return False

        last_row = data.slice(-1, 1).to_dicts()[0]
        if last_row["ema_crossover"] != 1:
            return False

        window = data.slice(-self.alignment_window_size, self.alignment_window_size)
        rsi_below_threshold = window["rsi"].min() < self.rsi_oversold_threshold

        return rsi_below_threshold
