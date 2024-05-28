import tulipy as tp
import numpy as np

from investing_algorithm_framework import Algorithm, TradingStrategy, \
    TimeUnit, OrderSide, CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource

btc_eur_ohlcv_2h_data = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR_ohlcv_2h",
    symbol="BTC/EUR",
    market="BITVAVO",
    timeframe="2h",
    window_size=200,
)

btc_eur_ticker_data = CCXTTickerMarketDataSource(
    identifier="BTC/EUR_ticker",
    symbol="BTC/EUR",
    market="BITVAVO",
    backtest_timeframe="2h"
)

def is_below_trend(fast_series, slow_series):
    return fast_series[-1] < slow_series[-1]


def is_above_trend(fast_series, slow_series):
    return fast_series[-1] > slow_series[-1]


class Strategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [
        btc_eur_ohlcv_2h_data,
        btc_eur_ticker_data
    ]
    symbols = ["BTC/EUR"]

    def __init__(
        self,
        short_period,
        long_period
    ):
        self.fast = short_period
        self.slow = long_period
        super().__init__()

    def apply_strategy(self, algorithm: Algorithm, market_data):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]

            if algorithm.has_open_orders(target_symbol):
                continue

            df = market_data[f"{symbol}_ohlcv_2h"].to_pandas()
            df = self.add_ema(df, "Close", self.fast)
            df = self.add_ema(df, "Close", self.slow)
            ticker_data = market_data[f"{symbol}_ticker"]
            price = ticker_data['bid']

            if not algorithm.has_position(target_symbol) \
                    and self.is_crossover(
                df, f"EMA_Close_{self.fast}", f"EMA_Close_{self.slow}"
            ):
                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )

            if algorithm.has_position(target_symbol) \
                    and self.is_below_trend(
                df, f"EMA_Close_{self.fast}", f"EMA_Close_{self.slow}"
            ):
                open_trades = algorithm.get_open_trades(
                    target_symbol=target_symbol
                )
                for trade in open_trades:
                    algorithm.close_trade(trade)

    def is_below_trend(self, data, fast_key, slow_key):
        """
        Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
        With the given date time it will check if the ma_<period_one> is a
        crossover with the ma_<period_two>
        """
        return data[fast_key].iloc[-1] < data[slow_key].iloc[-1]

    def is_crossover(self, data, fast_key, slow_key):
        """
        Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
        With the given date time it will check if the ma_<period_one> is a
        crossover with the ma_<period_two>
        """
        return data[fast_key].iloc[-2] <= data[slow_key].iloc[-2] \
               and data[fast_key].iloc[-1] > data[slow_key].iloc[-1]

    def add_ema(self, data, key, period):
        data[f"EMA_{key}_{period}"] = tp.ema(data[key].to_numpy(), period)
        return data


def create_algorithm(
    name,
    description,
    short_period,
    long_period
) -> Algorithm:
    algorithm = Algorithm(
        name=name,
        description=description
    )
    algorithm.add_strategy(
        Strategy(
            short_period,
            long_period,
        )
    )
    return algorithm
