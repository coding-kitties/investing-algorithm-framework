import numpy as np
import polars as pl
import tulipy as tp
import logging
from investing_algorithm_framework import TimeUnit, TradingStrategy, \
    Algorithm, CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource

logger = logging.getLogger(__name__)

# Ohlcv data source
btc_eur_ohlcv_2h_data = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR_ohlcv_2h",
    symbol="BTC/EUR",
    market="BITVAVO",
    timeframe="2h",
    window_size=200,
)

# Ticker data source
btc_eur_ticker_data = CCXTTickerMarketDataSource(
    identifier="BTC/EUR_ticker",
    symbol="BTC/EUR",
    market="BITVAVO",
    backtest_timeframe="2h"
)

def is_rsi_lower_then(rsi, value):
    return rsi[-1] < value


def is_rsi_higher_then(rsi, value):
    return rsi[-1] > value


def is_rsi_increasing_by_at_least_average(
    rsi, average_increase=3, number_of_periods=3
):
    """
    Function to check if the rsi is increasing by at least the average
    increase in the given number of periods.
    :param rsi: RSI values
    :param average_decrease: Average decrease required
    :param number_of_periods: Number of periods to consider
    :return: True if RSI is decreasing by at least the average decrease,
    False otherwise
    """
    # Calculate the changes in RSI values
    rsi_changes = np.diff(rsi[-number_of_periods:])

    # Check if all changes are negative and their mean is less than or
    # equal to the average decrease
    return (rsi_changes > 0).all() and np.mean(rsi_changes) >= average_increase


def is_rsi_decreasing_by_at_least_average(
    rsi, average_decrease=3, number_of_periods=3
):
    """
    Function to check if the rsi is decreasing by at least the average
    decrease in the given number of periods.
    :param rsi: RSI values
    :param average_decrease: Average decrease required
    :param number_of_periods: Number of periods to consider
    :return: True if RSI is decreasing by at least the average decrease,
    False otherwise
    """
    # Calculate the changes in RSI values
    rsi_changes = np.diff(rsi[-number_of_periods:])

    # Check if all changes are negative and their mean is less than or equal
    # to the average decrease
    return (rsi_changes < 0).all() and np.mean(rsi_changes) \
           <= -average_decrease


def is_crossover(fast_series, slow_series):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossover with the ma_<period_two>
    """

    return fast_series[-2] <= slow_series[-2] \
           and fast_series[-1] > slow_series[-1]


def is_crossunder(fast_series, slow_series):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossover with the ma_<period_two>
    """

    return fast_series[-2] >= slow_series[-2] \
           and fast_series[-1] < slow_series[-1]


def is_below_trend(fast_series, slow_series):
    return fast_series[-1] < slow_series[-1]


def is_above_trend(fast_series, slow_series):
    return fast_series[-1] > slow_series[-1]


class CatchingBottomStrategy(TradingStrategy):
    time_unit = TimeUnit.MINUTE
    interval = 15
    market_data_sources = [
        btc_eur_ohlcv_2h_data,
        btc_eur_ticker_data
    ]
    symbols = ["BTC/EUR"]
    stop_loss_percentage = None
    rsi_value_buy_range = None
    rsi_value_sell_range = None

    def __init__(
        self,
        stop_loss_percentage,
        rsi_value_buy_range_above_trend,
        rsi_value_sell_range_above_trend,
        rsi_value_buy_range_below_trend,
        rsi_value_sell_range_below_trend,
        net_gain_percentage_below_trend,
        net_gain_percentage_above_trend,
        fast_trend,
        slow_trend
    ):
        super().__init__()
        self.stop_loss_percentage = stop_loss_percentage
        self.rsi_value_buy_range_above_trend = rsi_value_buy_range_above_trend
        self.rsi_value_sell_range_above_trend = rsi_value_sell_range_above_trend
        self.rsi_value_buy_range_below_trend = rsi_value_buy_range_below_trend
        self.rsi_value_sell_range_below_trend = rsi_value_sell_range_below_trend
        self.net_gain_percentage_below_trend = net_gain_percentage_below_trend
        self.net_gain_percentage_above_trend = net_gain_percentage_above_trend
        self.fast_trend = fast_trend
        self.slow_trend = slow_trend

    def apply_strategy(self, algorithm: Algorithm, market_data):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]

            if algorithm.has_open_orders(target_symbol):
                continue

            df = market_data[f"{symbol}_ohlcv_2h"]
            fast = tp.ema(df['Close'].to_numpy(), period=self.fast_trend)
            slow = tp.sma(df['Close'].to_numpy(), period=self.slow_trend)

            if df is not None and len(df) > 0:

                if is_below_trend(fast, slow):
                    rsi_value_buy_range = self.rsi_value_buy_range_below_trend
                    rsi_value_sell_range = \
                        self.rsi_value_sell_range_below_trend
                    net_gain_percentage = \
                        self.net_gain_percentage_below_trend
                else:
                    rsi_value_buy_range = \
                        self.rsi_value_buy_range_above_trend
                    rsi_value_sell_range = \
                        self.rsi_value_sell_range_above_trend
                    net_gain_percentage = \
                        self.net_gain_percentage_above_trend

                df = df.with_columns(
                    pl.col('Datetime') \
                        .str \
                        .to_datetime(format="%Y-%m-%d %H:%M:%S")
                )
                rsi = tp.rsi(df['Close'].to_numpy(), period=14)
                price = market_data[f"{symbol}_ticker"]["bid"]

                if not algorithm.has_position(target_symbol) and \
                        is_rsi_lower_then(rsi, rsi_value_buy_range) and \
                        is_rsi_decreasing_by_at_least_average(
                            rsi, average_decrease=4, number_of_periods=4
                        ):
                    algorithm.create_limit_order(
                        target_symbol=target_symbol,
                        order_side="BUY",
                        price=price,
                        percentage_of_portfolio=18,
                        precision=4
                    )

                if algorithm.has_position(target_symbol) \
                        and is_rsi_higher_then(
                            rsi, value=rsi_value_sell_range
                        ) \
                        and is_rsi_increasing_by_at_least_average(
                    rsi,
                    average_increase=4,
                    number_of_periods=4
                ):

                    open_trades = algorithm.get_open_trades(target_symbol)

                    for open_trade in open_trades:

                        if open_trade.net_gain_percentage > net_gain_percentage:
                            algorithm.close_trade(open_trade)

            # Checking manual stop losses
            open_trades = algorithm.get_open_trades(target_symbol)

            for open_trade in open_trades:
                if open_trade.is_manual_stop_loss_trigger(
                        ohlcv_df=df,
                        current_price=market_data[f"{symbol}_ticker"]["bid"],
                        stop_loss_percentage=self.stop_loss_percentage
                ):
                    algorithm.close_trade(open_trade)


def create_algorithm(
    name,
    context,
    stop_loss_percentage=4,
    rsi_value_buy_range_above_trend=40,
    rsi_value_sell_range_above_trend=80,
    rsi_value_buy_range_below_trend=10,
    rsi_value_sell_range_below_trend=50,
    net_gain_percentage_below_trend=5,
    net_gain_percentage_above_trend=1,
    fast_trend=50,
    slow_trend=100
):
    algorithm = Algorithm(
        name=name,
        context=context,
        strategy=CatchingBottomStrategy(
            stop_loss_percentage,
            rsi_value_buy_range_above_trend,
            rsi_value_sell_range_above_trend,
            rsi_value_buy_range_below_trend,
            rsi_value_sell_range_below_trend,
            net_gain_percentage_below_trend,
            net_gain_percentage_above_trend,
            fast_trend,
            slow_trend
        ),
    )
    return algorithm
