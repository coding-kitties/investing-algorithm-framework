import pathlib
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, TimeUnit, \
    TradingTimeFrame, TradingDataType, TradingStrategy, \
    RESOURCE_DIRECTORY, pretty_print_backtest, Algorithm, \
    OrderSide


class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 24
    trading_data_types = [TradingDataType.OHLCV, TradingDataType.TICKER]
    trading_time_frame_start_date = datetime.utcnow() - timedelta(days=365)
    trading_time_frame = TradingTimeFrame.ONE_DAY
    market = "BITVAVO"
    symbols = ["BTC/EUR"]

    def apply_strategy(
        self,
        algorithm: Algorithm,
        market_data,
    ):
        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]
            price = market_data[TradingDataType.TICKER][symbol]["bid"]

            if algorithm.has_open_orders(target_symbol):
                continue

            if not algorithm.has_position(target_symbol):
                algorithm.create_limit_order(
                    target_symbol,
                    order_side=OrderSide.BUY,
                    percentage_of_portfolio=25,
                    price=price
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
