import pathlib
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, TimeUnit, \
    TradingTimeFrame, TradingDataType, TradingStrategy, \
    RESOURCE_DIRECTORY, pretty_print_backtest


class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 24
    trading_data_type = TradingDataType.OHLCV
    trading_time_frame_start_date = datetime.utcnow() - timedelta(days=365)
    trading_time_frame = TradingTimeFrame.ONE_DAY
    market = "BITVAVO"
    symbols = ["BTC/EUR"]

    def apply_strategy(
        self,
        algorithm,
        market_data,
    ):
        print(len(algorithm.get_orders()))
        print(market_data)


class MyTradingStrategyTwo(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 3
    trading_data_type = TradingDataType.OHLCV
    trading_time_frame_start_date = datetime.utcnow() - timedelta(days=1)
    trading_time_frame = TradingTimeFrame.ONE_MINUTE
    market = "BITVAVO"
    symbols = ["BTC/EUR"]

    def apply_strategy(
        self,
        algorithm,
        market_data,
    ):
        # print(len(algorithm.get_orders()))
        print(market_data)

# No resource directory specified, so an in-memory database will be used
app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_strategy(MyTradingStrategy)
# app.add_strategy(MyTradingStrategyTwo)

if __name__ == "__main__":
    backtest_reports = app.backtest(
        start_date=datetime.utcnow() - timedelta(days=9),
        end_date=datetime.utcnow(),
        unallocated=1000,
        trading_symbol="EUR"
    )
    pretty_print_backtest(backtest_reports)
