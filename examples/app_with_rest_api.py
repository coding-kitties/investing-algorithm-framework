import pathlib

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit, MarketCredential

app = create_app(
    {RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()}, web=True
)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your_market>",
        trading_symbol="<your_trading_symbol>"
    )
)
app.add_market_credential(
    MarketCredential(
        market="<your_market>",
        api_key="<your_api_key>",
        secret_key="<your_secret_key>"
    )
)


@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm, market_data):
    pass


if __name__ == "__main__":
    app.run()
