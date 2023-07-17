import pathlib

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit

app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your_market>",
        api_key="<your_api_key>",
        secret_key="<your_secret_key>",
        trading_symbol="<your_trading_symbol>"
    )
)


@app.strategy(
    time_unit=TimeUnit.SECOND,
    interval=5,
    market="BINANCE",
)
def perform_strategy(algorithm, market_data):
    print(algorithm.get_orders())

    for order in algorithm.get_orders():
        algorithm.place_order(order)
    print(len(algorithm.get_orders()))
    print(market_data)


if __name__ == "__main__":
    app.run()
