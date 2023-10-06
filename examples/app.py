import pathlib

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit, TradingDataType, TradingTimeFrame
from datetime import datetime, timedelta

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
    market="BITVAVO",
    trading_data_types=[TradingDataType.OHLCV, TradingDataType.TICKER],
    trading_time_frame=TradingTimeFrame.ONE_DAY,
    symbols=["BTC/EUR"],
    trading_time_frame_start_date=datetime.now() - timedelta(days=60),
)
def perform_strategy(algorithm, market_data):
    print(algorithm.get_portfolio())
    print(algorithm.get_positions())
    print(algorithm.get_orders())
    print(market_data)

    if algorithm.position_exists("<symbol>"):
        algorithm.close_position("<symbol>")
    else:
        algorithm.create_limit_order(
            symbol="<symbol>",
            side="buy",
            percentage_portfolio=20,
            price=market_data["tickers"]["<symbol>"]["bid"]
        )


if __name__ == "__main__":
    app.run()
