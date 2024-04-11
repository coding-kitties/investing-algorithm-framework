import tulipy as ti

from investing_algorithm_framework import TimeUnit, TradingStrategy, \
    Algorithm, OrderSide, BACKTESTING_INDEX_DATETIME

"""
This strategy is based on the golden cross strategy. It will buy when the
fast moving average crosses the slow moving average from below. It will sell
when the fast moving average crosses the slow moving average from above.

The strategy will also check if the fast moving average is above the trend
moving average. If it is not above the trend moving average it will not buy.

It uses tulipy indicators to calculate the metrics. You need to 
install this library in your environment to run this strategy.
You can find instructions on how to install tulipy here:
https://tulipindicators.org/ or go directly to the pypi page:
https://pypi.org/project/tulipy/
"""
def is_below_trend(fast_series, slow_series):
    return fast_series[-1] < slow_series[-1]


def is_above_trend(fast_series, slow_series):
    return fast_series[-1] > slow_series[-1]


def is_crossover(fast, slow):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossover with the ma_<period_two>
    """
    return fast[-2] <= slow[-2] and fast[-1] > slow[-1]


def is_crossunder(fast, slow):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossover with the ma_<period_two>
    """
    return fast[-2] >= slow[-2] and fast[-1] < slow[-1]


class CrossOverStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [
        "BTC/EUR-ohlcv",
        "DOT/EUR-ohlcv",
        "BTC/EUR-ticker",
        "DOT/EUR-ticker"
    ]
    symbols = ["BTC/EUR", "DOT/EUR"]
    fast = 21
    slow = 75
    trend = 150
    stop_loss_percentage = 7

    def apply_strategy(self, algorithm: Algorithm, market_data):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]

            if algorithm.has_open_orders(target_symbol):
                continue

            df = market_data[f"{symbol}-ohlcv"]
            ticker_data = market_data[f"{symbol}-ticker"]
            fast = ti.sma(df['Close'].to_numpy(), self.fast)
            slow = ti.sma(df['Close'].to_numpy(), self.slow)
            trend = ti.sma(df['Close'].to_numpy(), self.trend)
            price = ticker_data["bid"]

            if not algorithm.has_position(target_symbol) \
                    and is_crossover(fast, slow) \
                    and is_above_trend(fast, trend):
                print(f"opening trade on {algorithm.config['BACKTESTING_INDEX_DATETIME']} with price {price}")

                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )

            if algorithm.has_position(target_symbol) \
                and is_below_trend(fast, slow):
                print(f"closing trade on {algorithm.config['BACKTESTING_INDEX_DATETIME']} with price {price}")
                open_trades = algorithm.get_open_trades(
                    target_symbol=target_symbol
                )

                for trade in open_trades:
                    algorithm.close_trade(trade)

            # Checking manual stop losses
            open_trades = algorithm.get_open_trades(target_symbol)

            for open_trade in open_trades:
                if open_trade.is_manual_stop_loss_trigger(
                    ohlcv_df=df,
                    current_price=market_data[f"{symbol}-ticker"]["bid"],
                    stop_loss_percentage=self.stop_loss_percentage
                ):
                    print(f"stop los triggered on {algorithm.config['BACKTESTING_INDEX_DATETIME']} with price {price} ")
                    algorithm.close_trade(open_trade)
