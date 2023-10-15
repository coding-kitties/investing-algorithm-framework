import pathlib
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, TradingTimeFrame, TradingDataType, TradingStrategy, \
    RESOURCE_DIRECTORY


class MyTradingStrategy(TradingStrategy):
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
        print(len(algorithm.get_orders()))
        print(market_data)


# No resource directory specified, so an in-memory database will be used
app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
# app.add_portfolio_configuration(
#     PortfolioConfiguration(
#         market="bitvavo",
#         api_key="<your_api_key>",
#         secret_key="<your_secret_key>",
#         trading_symbol="EUR"
#     )
# )
app.add_strategy(MyTradingStrategy)

if __name__ == "__main__":
    report = app.backtest(
        start_date=datetime.utcnow() - timedelta(days=1),
        end_date=datetime.utcnow(),
        unallocated=1000,
        trading_symbol="EUR"
    )
    # pretty_print_report(report)
    # print(report.get_orders())
    # print(report.get_trades())
    # print(report.get_positions())
    #
    # report = app.backtest(
    #     start_datetime=datetime.utcnow() - timedelta(days=1),
    #     end_datetime=datetime.utcnow(),
    #     source="ccxt",
    #     unallocated=10000,
    #     commission=0.001,
    #     commission_currency="EUR"
    # )
    # pretty_print_report(report)
