import logging.config
import time
from datetime import datetime, timedelta

from pyindicators import ema, is_crossover, is_above, is_below, is_crossunder

from investing_algorithm_framework import (
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, create_app,
    pretty_print_backtest, BacktestDateRange, TimeUnit, TradingStrategy,
    OrderSide, DEFAULT_LOGGING_CONFIG, Context
)

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)


"""
This strategy is based on the golden cross strategy. It will buy when the
fast moving average crosses the slow moving average from below. It will sell
when the fast moving average crosses the slow moving average from above.
The strategy will also check if the fast moving average is above the trend
moving average. If it is not above the trend moving average it will not buy.

It uses pyindicators to calculate the metrics. You need to
install this library in your environment to run this strategy.
You can find instructions on how to install tulipy here:
https://github.com/coding-kitties/PyIndicators or go directly
to the pypi page: https://pypi.org/project/PyIndicators/
"""

bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv-2h",
    market="BINANCE",
    symbol="BTC/EUR",
    time_frame="2h",
    window_size=200
)
bitvavo_dot_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="DOT/EUR-ohlch-2h",
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

class CrossOverStrategy(TradingStrategy):
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
    time_unit = TimeUnit.HOUR
    interval = 2
    symbol_pairs = ["BTC/EUR"]
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]
    fast = 50
    slow = 100
    trend = 200
    stop_loss_percentage = 2
    stop_loss_sell_size = 50
    take_profit_percentage = 8
    take_profit_sell_size = 50

    def apply_strategy(self, context: Context, market_data):

        for pair in self.symbol_pairs:
            symbol = pair.split('/')[0]

            # Don't trade if there are open orders for the symbol
            # This is important to avoid placing new orders while there are
            # existing orders that are not yet filled
            if context.has_open_orders(symbol):
                continue

            ohlvc_data = market_data[f"{pair}-ohlcv-2h"]
            # ticker_data = market_data[f"{symbol}-ticker"]
            # Add fast, slow, and trend EMAs to the data
            ohlvc_data = ema(
                ohlvc_data,
                source_column="Close",
                period=self.fast,
                result_column=f"ema_{self.fast}"
            )
            ohlvc_data = ema(
                ohlvc_data,
                source_column="Close",
                period=self.slow,
                result_column=f"ema_{self.slow}"
            )
            ohlvc_data = ema(
                ohlvc_data,
                source_column="Close",
                period=self.trend,
                result_column=f"ema_{self.trend}"
            )

            price = ohlvc_data["Close"][-1]

            if not context.has_position(symbol) \
                    and self._is_buy_signal(ohlvc_data):
                order = context.create_limit_order(
                    target_symbol=symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
                trade = context.get_trade(order_id=order.id)
                context.add_stop_loss(
                    trade=trade,
                    trade_risk_type="trailing",
                    percentage=self.stop_loss_percentage,
                    sell_percentage=self.stop_loss_sell_size
                )
                context.add_take_profit(
                    trade=trade,
                    percentage=self.take_profit_percentage,
                    trade_risk_type="trailing",
                    sell_percentage=self.take_profit_sell_size
                )

            if context.has_position(symbol) \
                    and self._is_sell_signal(ohlvc_data):
                open_trades = context.get_open_trades(
                    target_symbol=symbol
                )

                for trade in open_trades:
                    context.close_trade(trade)

    def _is_sell_signal(self, data):
        return is_crossunder(
            data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.slow}",
            number_of_data_points=2
        ) and is_below(
            data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.trend}",
        )

    def _is_buy_signal(self, data):
        return is_crossover(
            data=data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.slow}",
            number_of_data_points=2
        ) and is_above(
            data=data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.trend}",
        )


app = create_app(name="GoldenCrossStrategy")
app.add_market(
    market="BINANCE", trading_symbol="EUR", initial_balance=400,
)
app.add_strategy(CrossOverStrategy)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_dot_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)
app.add_market_data_source(bitvavo_dot_eur_ticker)


if __name__ == "__main__":
    end_date = datetime(2023, 12, 2)
    start_date = end_date - timedelta(days=100)
    date_range = BacktestDateRange(
        start_date=start_date,
        end_date=end_date
    )
    start_time = time.time()
    backtest_report = app.run_backtest(
        backtest_date_range=date_range, save_in_memory_strategies=True
    )
    pretty_print_backtest(backtest_report)
    end_time = time.time()
    print(f"Execution Time: {end_time - start_time:.6f} seconds")
