from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, Task, MarketCredential

# No resource directory specified, so an in-memory database will be used
app = create_app()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your_market>",
        trading_symbol="<your_trading_symbol>"
    )
)
app.add_market_credential(
    MarketCredential(
        api_key="<your_api_key>",
        market="<your_market>",
        secret_key="<your_secret_key>"
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
    time_unit=TimeUnit.SECOND, interval=5
)
def perform_strategy(algorithm, market_data):
    pass


if __name__ == "__main__":
    app.run()
