from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, TradingTimeFrame, TradingDataType, Task, StatelessAction

# No resource directory specified, so an in-memory database will be used
app = create_app(stateless=True)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your_market>",
        api_key="<your_api_key>",
        secret_key="<your_secret_key>",
        trading_symbol="<your_trading_symbol>"
    )
)


class MyTask(Task):
    time_unit = TimeUnit.SECOND
    interval = 5

    def run(self, algorithm):
        print("Hello world from MyTask")


class MyTaskTwo(Task):
    time_unit = TimeUnit.SECOND
    interval = 5

    def run(self, algorithm):
        print("Hello world from MyTaskTwo")


app.add_task(MyTask)
app.add_task(MyTaskTwo)


@app.task(time_unit=TimeUnit.SECOND, interval=5)
def say_hello(algorithm):
    print("Hello world")


@app.strategy(
    time_unit=TimeUnit.SECOND,
    interval=5,
    market="BINANCE",
    symbols=["BTC/EUR"],
    trading_data_types=[TradingDataType.OHLCV],
    trading_time_frame_start_date=datetime.utcnow() - timedelta(days=1),
    trading_time_frame=TradingTimeFrame.ONE_MINUTE
)
def perform_strategy(algorithm, market_data):
    print(len(algorithm.get_orders()))


if __name__ == "__main__":
    app.run(payload={
        "ACTION": StatelessAction.RUN_STRATEGY
    })
