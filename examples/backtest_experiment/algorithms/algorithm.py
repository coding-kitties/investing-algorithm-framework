from investing_algorithm_framework import Algorithm, TradingStrategy, \
    TimeUnit, OrderSide, DATETIME_FORMAT
import tulipy as ti
import polars as pl


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


class Strategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [
        "BTC/EUR-ohlcv",
        "DOT/EUR-ohlcv",
        "BTC/EUR-ticker",
        "DOT/EUR-ticker"
    ]
    symbols = ["BTC/EUR", "DOT/EUR"]

    def __init__(self, fast, slow, trend, stop_loss_percentage=4):
        self.fast = fast
        self.slow = slow
        self.trend = trend
        self.stop_loss_percentage = stop_loss_percentage
        super().__init__()

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
            price = ticker_data['bid']

            if not algorithm.has_position(target_symbol) \
                    and is_crossover(fast, slow) \
                    and is_above_trend(fast, trend):
                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )

            if algorithm.has_position(target_symbol) \
                    and is_below_trend(fast, slow):

                open_trades = algorithm.get_open_trades(
                    target_symbol=target_symbol
                )

                for trade in open_trades:
                    algorithm.close_trade(trade)

            # Checking manual stop losses
            open_trades = algorithm.get_open_trades(target_symbol)

            for open_trade in open_trades:
                filtered_df = df.filter(
                    pl.col('Datetime') >= open_trade.opened_at.strftime(DATETIME_FORMAT)
                )
                close_prices = filtered_df['Close'].to_numpy()
                current_price = market_data[f"{symbol}-ticker"]

                if open_trade.is_manual_stop_loss_trigger(
                        prices=close_prices,
                        current_price=current_price["bid"],
                        stop_loss_percentage=self.stop_loss_percentage
                ):
                    algorithm.close_trade(open_trade)


def create_algorithm(
    name,
    description,
    fast,
    slow,
    trend,
    stop_loss_percentage
) -> Algorithm:
    algorithm = Algorithm(
        name=name,
        description=description
    )
    algorithm.add_strategy(Strategy(fast, slow, trend, stop_loss_percentage))
    return algorithm
