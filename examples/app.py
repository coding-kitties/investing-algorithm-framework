import pathlib

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit, TradingDataType, TradingTimeFrame
from datetime import datetime, timedelta

app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="bitvavo",
        api_key="0103327416b10ec50bd6776b2f1e313174fbbb85bdfb9bdbfa47ea6823d4c5e4",
        secret_key="3c73f7917f80b54908bcc6adb356f75beaf14fc27ec8f4a0f672d90a02b3d013d4a89eef124be7ecfe14f3cb76add950d546d3c86b0eaf5af244d8b2d353d44f",
        trading_symbol="EUR"
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
