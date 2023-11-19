import pathlib
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, TimeUnit, \
    TradingTimeFrame, TradingDataType, TradingStrategy, \
    RESOURCE_DIRECTORY, pretty_print_backtest, Algorithm, \
    OrderType, OrderSide
from investing_algorithm_framework.domain import BACKTESTING_INDEX_DATETIME


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
        algorithm: Algorithm,
        market_data,
    ):
        price = market_data["ohlcvs"]["BTC/EUR"][-1][3]

        if not algorithm.has_open_orders("BTC") and not algorithm.has_position("BTC"):
            algorithm.create_order(
                "BTC", price, OrderType.LIMIT, OrderSide.BUY, amount=0.002
            )


app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_strategy(MyTradingStrategy)


if __name__ == "__main__":
    backtest_reports = app.backtest(
        start_date=datetime(2023, 11, 12) - timedelta(days=9),
        end_date=datetime(2023, 11, 12),
        unallocated=400,
        trading_symbol="EUR"
    )
    pretty_print_backtest(backtest_reports)
