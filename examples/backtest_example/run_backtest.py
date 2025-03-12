import time
from datetime import datetime
import logging.config
from datetime import datetime, timedelta


from investing_algorithm_framework import CCXTOHLCVMarketDataSource, \
    CCXTTickerMarketDataSource, PortfolioConfiguration, \
    create_app, pretty_print_backtest, BacktestDateRange, TimeUnit, \
    TradingStrategy, OrderSide, DEFAULT_LOGGING_CONFIG, Context

import tulipy as ti

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)


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

bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="BINANCE",
    symbol="BTC/EUR",
    time_frame="2h",
    window_size=200
)
bitvavo_dot_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="DOT/EUR-ohlcv",
    market="BINANCE",
    symbol="DOT/EUR",
    time_frame="2h",
    window_size=200
)
bitvavo_dot_eur_ticker = CCXTTickerMarketDataSource(
    identifier="DOT/EUR-ticker",
    market="BINANCE",
    symbol="DOT/EUR",
    backtest_time_frame="2h",
)
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="BINANCE",
    symbol="BTC/EUR",
    backtest_time_frame="2h",
)


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
        bitvavo_dot_eur_ticker,
        bitvavo_btc_eur_ticker,
        bitvavo_dot_eur_ohlcv_2h,
        bitvavo_btc_eur_ohlcv_2h
    ]
    symbols = ["BTC/EUR", "DOT/EUR"]
    fast = 21
    slow = 75
    trend = 150
    stop_loss_percentage = 7

    def apply_strategy(self, context: Context, market_data):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]

            if context.has_open_orders(target_symbol):
                continue

            df = market_data[f"{symbol}-ohlcv"]
            ticker_data = market_data[f"{symbol}-ticker"]
            fast = ti.sma(df['Close'].to_numpy(), self.fast)
            slow = ti.sma(df['Close'].to_numpy(), self.slow)
            trend = ti.sma(df['Close'].to_numpy(), self.trend)
            price = ticker_data["bid"]

            if not context.has_position(target_symbol) \
                    and is_crossover(fast, slow) \
                    and is_above_trend(fast, trend):
                order = context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
                trade = context.get_trade(order_id=order.id)
                context.add_stop_loss(
                    trade=trade,
                    trade_risk_type="trailing",
                    percentage=5,
                    sell_percentage=50
                )
                context.add_take_profit(
                    trade=trade,
                    percentage=5,
                    trade_risk_type="trailing",
                    sell_percentage=50
                )
                context.add_take_profit(
                    trade=trade,
                    percentage=10,
                    trade_risk_type="trailing",
                    sell_percentage=20
                )

            if context.has_position(target_symbol) \
                    and is_below_trend(fast, slow):
                open_trades = context.get_open_trades(
                    target_symbol=target_symbol
                )

                for trade in open_trades:
                    context.close_trade(trade)


app = create_app(name="GoldenCrossStrategy")
app.add_strategy(CrossOverStrategy)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_dot_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)
app.add_market_data_source(bitvavo_dot_eur_ticker)

# Add a portfolio configuration of 400 euro initial balance
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BINANCE",
        trading_symbol="EUR",
        initial_balance=400,
    )
)

if __name__ == "__main__":
    end_date = datetime(2023, 12, 2)
    start_date = end_date - timedelta(days=100)
    date_range = BacktestDateRange(
        start_date=start_date,
        end_date=end_date
    )
    start_time = time.time()
    backtest_report = app.run_backtest(backtest_date_range=date_range)
    pretty_print_backtest(backtest_report)
    end_time = time.time()
    print(f"Execution Time: {end_time - start_time:.6f} seconds")
